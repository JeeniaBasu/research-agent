"""
=============================================================================
services/rag_service.py — Retrieval-Augmented Generation (RAG) Service
=============================================================================
Implements RAG to ground LLM responses in retrieved research papers.
Uses TF-IDF + cosine similarity for efficient in-memory vector retrieval.
Reduces hallucinations by injecting relevant paper excerpts into prompts.
=============================================================================
"""

import logging
import re
from typing import Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import AGENT_INSTRUCTIONS

logger = logging.getLogger(__name__)


class RAGService:
    """
    Lightweight RAG service using TF-IDF vector store.

    Workflow:
    1. Index papers (convert to searchable TF-IDF vectors)
    2. Query — find top-k most relevant paper chunks
    3. Format context string to inject into LLM prompts
    """

    def __init__(self):
        self._vectorizer = TfidfVectorizer(
            max_features=10000,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        self._doc_vectors = None
        self._documents: list = []          # List of (paper_id, chunk_text, paper_meta)
        self._is_fitted: bool = False
        self._confidence_threshold: float = (
            AGENT_INSTRUCTIONS["hallucination_prevention"]["confidence_threshold"]
        )
        self._max_context_papers: int = (
            AGENT_INSTRUCTIONS["hallucination_prevention"]["max_context_papers"]
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_papers(self, papers: list) -> int:
        """
        Index a list of paper dicts into the TF-IDF store.
        Chunks each paper into title+abstract segments.

        Returns:
            Number of documents indexed.
        """
        if not papers:
            return 0

        new_docs = []
        for paper in papers:
            chunks = self._chunk_paper(paper)
            for chunk_text in chunks:
                new_docs.append({
                    "id": paper.get("id", ""),
                    "text": chunk_text,
                    "paper": paper,
                })

        if not new_docs:
            return 0

        # Merge with existing documents (avoid re-indexing duplicates)
        existing_ids = {d["id"] for d in self._documents}
        for doc in new_docs:
            if doc["id"] not in existing_ids:
                self._documents.append(doc)

        # Re-fit the vectorizer
        self._refit()
        logger.info("RAG store: indexed %d papers → %d documents total",
                    len(papers), len(self._documents))
        return len(new_docs)

    def _refit(self) -> None:
        """Refit the TF-IDF vectorizer on all indexed documents."""
        if not self._documents:
            return
        texts = [d["text"] for d in self._documents]
        try:
            self._doc_vectors = self._vectorizer.fit_transform(texts)
            self._is_fitted = True
        except Exception as exc:
            logger.error("RAG refit error: %s", exc)
            self._is_fitted = False

    def clear(self) -> None:
        """Clear the document store (e.g., when starting a new research session)."""
        self._documents.clear()
        self._doc_vectors = None
        self._is_fitted = False
        logger.info("RAG store cleared.")

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = None) -> list:
        """
        Retrieve the most relevant paper chunks for a query.

        Args:
            query: Natural language query string.
            top_k: Number of results to return (defaults to max_context_papers).

        Returns:
            List of dicts: {score, paper, text}
        """
        if not self._is_fitted or not self._documents:
            return []

        k = top_k or self._max_context_papers

        try:
            query_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self._doc_vectors).flatten()

            # Get top-k indices above confidence threshold
            top_indices = np.argsort(scores)[::-1]
            results = []
            seen_paper_ids = set()

            for idx in top_indices:
                score = float(scores[idx])
                if score < self._confidence_threshold:
                    break
                doc = self._documents[idx]
                paper_id = doc["id"]

                # One result per unique paper
                if paper_id not in seen_paper_ids:
                    seen_paper_ids.add(paper_id)
                    results.append({
                        "score": round(score, 4),
                        "paper": doc["paper"],
                        "text": doc["text"],
                    })

                if len(results) >= k:
                    break

            return results

        except Exception as exc:
            logger.error("RAG retrieval error: %s", exc)
            return []

    def build_context_string(self, query: str, papers: list = None) -> str:
        """
        Build a formatted context string to inject into an LLM prompt.

        Retrieves relevant chunks from the store. If papers are provided,
        also indexes them first (ensures freshly retrieved papers are available).

        Returns:
            A formatted string ready for prompt injection.
        """
        if not AGENT_INSTRUCTIONS["hallucination_prevention"]["rag_grounding"]:
            return ""

        if papers:
            self.index_papers(papers)

        results = self.retrieve(query)
        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            p = result["paper"]
            authors = ", ".join(p.get("authors", ["Unknown"])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."

            context_parts.append(
                f"[Source {i}] \"{p.get('title', 'Unknown')}\"\n"
                f"Authors: {authors} ({p.get('year', 'n.d.')})\n"
                f"Source: {p.get('source', 'Unknown')} | "
                f"Relevance: {result['score']:.2f}\n"
                f"{result['text']}\n"
            )

        return "\n---\n".join(context_parts)

    def get_context_papers(self, query: str, papers: list = None) -> list:
        """Return the actual paper objects most relevant to a query."""
        if papers:
            self.index_papers(papers)
        results = self.retrieve(query)
        return [r["paper"] for r in results]

    # ------------------------------------------------------------------
    # Document chunking
    # ------------------------------------------------------------------

    def _chunk_paper(self, paper: dict) -> list:
        """
        Split a paper into text chunks for indexing.
        Currently creates two chunks: a header chunk and an abstract chunk.
        """
        chunks = []
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        keywords = " ".join(paper.get("keywords", []))

        # Chunk 1: Full metadata (title + authors + keywords)
        authors_str = ", ".join(paper.get("authors", [])[:5])
        meta_chunk = f"{title} {authors_str} {keywords}".strip()
        if meta_chunk:
            chunks.append(meta_chunk)

        # Chunk 2: Abstract sentences
        if abstract:
            sentences = self._split_sentences(abstract)
            chunk_size = 3  # sentences per chunk
            for i in range(0, len(sentences), chunk_size):
                chunk = " ".join(sentences[i:i + chunk_size])
                if chunk.strip():
                    chunks.append(f"{title}: {chunk}")

        # Fallback
        if not chunks:
            chunks.append(title or paper.get("id", "unknown"))

        return chunks

    @staticmethod
    def _split_sentences(text: str) -> list:
        """Split text into sentences using simple regex."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def paper_count(self) -> int:
        if not self._documents:
            return 0
        return len({d["id"] for d in self._documents})
