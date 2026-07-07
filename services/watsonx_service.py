"""
=============================================================================
services/watsonx_service.py — IBM Watsonx.ai / Granite Integration
=============================================================================
Handles all interactions with IBM Granite models via the Watsonx.ai SDK.
Provides specialised methods for: chat, summarisation, literature review
generation, report drafting, and citation assistance.
=============================================================================
"""

import logging
from typing import Optional
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

from config import WatsonxConfig, AGENT_INSTRUCTIONS

logger = logging.getLogger(__name__)


class WatsonxService:
    """
    Singleton service wrapping IBM Watsonx.ai Foundation Model inference.
    All prompt engineering and LLM calls are centralised here.
    """

    def __init__(self):
        self._client: Optional[APIClient] = None
        self._chat_model: Optional[ModelInference] = None
        self._initialized: bool = False
        self._init_error: Optional[str] = None
        self._initialize()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """Authenticate and instantiate the Watsonx.ai client."""
        try:
            if not WatsonxConfig.API_KEY or WatsonxConfig.API_KEY == "your_ibm_cloud_api_key_here":
                raise ValueError("IBM_CLOUD_API_KEY is not configured in your .env file.")
            if not WatsonxConfig.PROJECT_ID or WatsonxConfig.PROJECT_ID == "your_watsonx_project_id_here":
                raise ValueError("WATSONX_PROJECT_ID is not configured in your .env file.")

            credentials = Credentials(
                url=WatsonxConfig.URL,
                api_key=WatsonxConfig.API_KEY,
            )
            self._client = APIClient(credentials=credentials)

            gen_params = {
                GenParams.MAX_NEW_TOKENS: WatsonxConfig.MAX_NEW_TOKENS,
                GenParams.TEMPERATURE: WatsonxConfig.TEMPERATURE,
                GenParams.TOP_P: WatsonxConfig.TOP_P,
                GenParams.REPETITION_PENALTY: WatsonxConfig.REPETITION_PENALTY,
            }

            self._chat_model = ModelInference(
                model_id=WatsonxConfig.CHAT_MODEL,
                params=gen_params,
                credentials=credentials,
                project_id=WatsonxConfig.PROJECT_ID,
            )

            self._initialized = True
            logger.info("✅ Watsonx.ai client initialised — model: %s", WatsonxConfig.CHAT_MODEL)

        except Exception as exc:
            self._init_error = str(exc)
            logger.error("❌ Watsonx.ai initialisation failed: %s", exc)

    @property
    def is_ready(self) -> bool:
        return self._initialized

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, system_context: str, user_message: str, rag_context: str = "") -> str:
        """
        Build a structured prompt using IBM Granite's instruct template.
        Injects RAG context when provided to ground the answer in real papers.
        """
        context_block = ""
        if rag_context:
            context_block = (
                f"\n\n<|context|>\n"
                f"The following retrieved research papers provide factual grounding "
                f"for your response. Rely on this information and cite it:\n\n"
                f"{rag_context}\n"
                f"<|end_context|>\n"
            )

        prompt = (
            f"<|system|>\n{system_context}{context_block}\n"
            f"<|user|>\n{user_message}\n"
            f"<|assistant|>\n"
        )
        return prompt

    def _call_model(self, prompt: str, max_tokens: int = None) -> str:
        """Execute an LLM call and return the generated text."""
        if not self._initialized:
            raise RuntimeError(
                f"Watsonx.ai service is not available: {self._init_error}"
            )
        try:
            params = {}
            if max_tokens:
                params[GenParams.MAX_NEW_TOKENS] = max_tokens

            response = self._chat_model.generate_text(
                prompt=prompt,
                params=params if params else None,
            )
            return response.strip()
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            raise RuntimeError(f"Model inference error: {exc}") from exc

    # ------------------------------------------------------------------
    # Public API — specialised research methods
    # ------------------------------------------------------------------

    def chat(self, user_message: str, rag_context: str = "", conversation_history: list = None) -> str:
        """
        General-purpose research chat.
        Incorporates conversation history and RAG context for continuity.
        """
        system_prompt = AGENT_INSTRUCTIONS["system_prompt"]

        # Build a condensed history block (last 6 turns)
        history_block = ""
        if conversation_history:
            recent = conversation_history[-6:]
            turns = []
            for turn in recent:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                turns.append(f"[{role.upper()}]: {content}")
            history_block = "\n\nConversation so far:\n" + "\n".join(turns)

        full_system = system_prompt + history_block
        prompt = self._build_prompt(full_system, user_message, rag_context)
        return self._call_model(prompt)

    def summarize_paper(self, paper: dict, detail_level: str = "medium") -> str:
        """
        Generate a structured summary of a single research paper.
        Extracts objectives, methodology, datasets, models, results,
        limitations, and future work as configured in AGENT_INSTRUCTIONS.
        """
        sections = AGENT_INSTRUCTIONS.get("summary_sections", [])
        sections_str = ", ".join(sections)

        length_map = {"short": 300, "medium": 600, "long": 1000}
        token_hint = length_map.get(detail_level, 600)

        paper_text = self._format_paper_for_prompt(paper)

        system = (
            f"{AGENT_INSTRUCTIONS['system_prompt']}\n\n"
            f"You are specialised in generating structured paper summaries. "
            f"Always cover these sections: {sections_str}. "
            f"Use markdown headers for each section. Target ~{token_hint} words."
        )

        user_msg = (
            f"Generate a comprehensive structured summary of this research paper:\n\n"
            f"{paper_text}\n\n"
            f"Structure your response with these sections:\n"
            f"## 📌 Overview\n## 🎯 Objectives\n## 🔬 Methodology\n"
            f"## 📊 Datasets & Models\n## 🧪 Experiments & Results\n"
            f"## ⚠️ Limitations\n## 🔮 Future Work\n## 💡 Key Contributions"
        )

        prompt = self._build_prompt(system, user_msg)
        return self._call_model(prompt, max_tokens=1500)

    def compare_papers(self, papers: list) -> str:
        """
        Compare multiple papers in a structured markdown table.
        Contrasts objectives, methods, datasets, results, and limitations.
        """
        if len(papers) < 2:
            return "Please provide at least 2 papers to compare."

        papers_block = ""
        for i, p in enumerate(papers[:6], 1):
            papers_block += f"\n### Paper {i}: {p.get('title', 'Unknown')}\n"
            papers_block += self._format_paper_for_prompt(p) + "\n"

        system = (
            f"{AGENT_INSTRUCTIONS['system_prompt']}\n\n"
            "You are expert at comparative analysis of research papers. "
            "Generate detailed markdown comparison tables with clear, factual contrasts."
        )

        user_msg = (
            f"Compare and contrast the following {len(papers[:6])} research papers. "
            f"Create structured markdown tables comparing:\n"
            f"1. Research objectives & contributions\n"
            f"2. Methodology & approach\n"
            f"3. Datasets used\n"
            f"4. Models & techniques\n"
            f"5. Key results & metrics\n"
            f"6. Limitations\n\n"
            f"After the tables, provide a narrative synthesis of key similarities, "
            f"differences, and which paper makes the strongest contribution and why.\n\n"
            f"Papers:\n{papers_block}"
        )

        prompt = self._build_prompt(system, user_msg)
        return self._call_model(prompt, max_tokens=2000)

    def generate_literature_review(self, papers: list, research_topic: str, rag_context: str = "") -> str:
        """
        Generate a comprehensive literature review from a set of papers.
        Covers all sections defined in AGENT_INSTRUCTIONS['review_sections'].
        """
        sections = AGENT_INSTRUCTIONS.get("review_sections", [])
        sections_str = "\n".join(f"- {s.replace('_', ' ').title()}" for s in sections)

        papers_block = ""
        for i, p in enumerate(papers[:15], 1):
            papers_block += f"\n**[{i}] {p.get('title', 'Unknown')}** ({p.get('year', 'n.d.')})\n"
            papers_block += f"Authors: {', '.join(p.get('authors', ['Unknown']))}\n"
            papers_block += f"Abstract: {p.get('abstract', 'Not available')[:400]}\n"

        system = (
            f"{AGENT_INSTRUCTIONS['system_prompt']}\n\n"
            "You are an expert academic writer specialising in literature reviews. "
            "Your reviews are thorough, well-structured, identify research gaps, "
            "and suggest future directions. Always cite papers using [1], [2], etc."
        )

        user_msg = (
            f"Write a comprehensive academic literature review on: **{research_topic}**\n\n"
            f"Include these sections:\n{sections_str}\n\n"
            f"Use the following {len(papers)} retrieved papers as your primary sources. "
            f"Cite them inline as [1], [2], etc. Identify themes, contradictions, "
            f"research gaps, and promising future directions.\n\n"
            f"Papers:\n{papers_block}"
        )

        prompt = self._build_prompt(system, user_msg, rag_context)
        return self._call_model(prompt, max_tokens=2048)

    def generate_report_section(self, section: str, context: dict, papers: list = None, rag_context: str = "") -> str:
        """
        Draft a specific section of a research paper
        (abstract, introduction, related work, methodology, etc.).
        """
        papers_ref = ""
        if papers:
            for i, p in enumerate(papers[:10], 1):
                papers_ref += f"[{i}] {p.get('title', 'Unknown')} ({p.get('year', 'n.d.')})\n"

        section_instructions = {
            "abstract": "Write a concise (150-250 word) academic abstract covering: background, objective, methodology, results, and conclusion.",
            "introduction": "Write a 3-5 paragraph introduction that establishes context, identifies the problem, reviews relevant work briefly, and states the paper's contribution.",
            "related_work": "Write a structured related work section covering relevant prior research, grouped by theme, citing the provided papers.",
            "methodology": "Write a detailed methodology section describing the research approach, experimental setup, and evaluation metrics.",
            "results": "Write a results section presenting findings clearly, with reference to tables and figures where appropriate.",
            "discussion": "Write a discussion section interpreting results, comparing with prior work, and addressing limitations.",
            "conclusion": "Write a conclusion summarising contributions, limitations, and future work directions.",
        }

        section_hint = section_instructions.get(
            section.lower(),
            f"Write the {section} section of a research paper."
        )

        system = (
            f"{AGENT_INSTRUCTIONS['system_prompt']}\n\n"
            "You are an expert academic writer. Write in formal academic style, "
            "use precise terminology, and cite sources appropriately."
        )

        user_msg = (
            f"Research Topic: {context.get('topic', 'Not specified')}\n"
            f"Section to write: {section.upper()}\n"
            f"Instructions: {section_hint}\n"
        )
        if context.get("notes"):
            user_msg += f"\nAdditional context/notes: {context['notes']}\n"
        if papers_ref:
            user_msg += f"\nAvailable references:\n{papers_ref}"

        prompt = self._build_prompt(system, user_msg, rag_context)
        return self._call_model(prompt, max_tokens=1500)

    def suggest_research_gaps(self, papers: list, topic: str) -> str:
        """Identify research gaps and suggest hypotheses and future directions."""
        papers_block = "\n".join(
            f"- {p.get('title', 'Unknown')} ({p.get('year', 'n.d.')}): {p.get('abstract', '')[:250]}"
            for p in papers[:10]
        )

        system = (
            f"{AGENT_INSTRUCTIONS['system_prompt']}\n\n"
            "You are a research strategist who excels at identifying gaps in the "
            "literature and formulating novel research hypotheses."
        )

        user_msg = (
            f"Based on these papers about '{topic}', identify:\n"
            f"1. **Research Gaps** — What has not been studied or is understudied?\n"
            f"2. **Contradictions** — Where do papers disagree or have conflicting results?\n"
            f"3. **Research Hypotheses** — 3-5 specific, testable hypotheses for future work.\n"
            f"4. **Future Directions** — Promising research directions and open problems.\n"
            f"5. **Methodology Opportunities** — Novel approaches that haven't been tried.\n\n"
            f"Papers:\n{papers_block}"
        )

        prompt = self._build_prompt(system, user_msg)
        return self._call_model(prompt, max_tokens=1500)

    def answer_followup(self, question: str, papers: list, rag_context: str = "") -> str:
        """Answer a follow-up question grounded in retrieved papers."""
        papers_titles = "\n".join(
            f"[{i}] {p.get('title', 'Unknown')}" for i, p in enumerate(papers[:8], 1)
        )

        system = (
            f"{AGENT_INSTRUCTIONS['system_prompt']}\n\n"
            "Answer questions accurately based on the provided papers. "
            "Cite paper numbers inline. State clearly if information is not available."
        )

        user_msg = (
            f"Question: {question}\n\n"
            f"Available papers:\n{papers_titles}\n\n"
            "Answer based on these papers. Use inline citations like [1], [2], etc."
        )

        prompt = self._build_prompt(system, user_msg, rag_context)
        return self._call_model(prompt, max_tokens=1000)

    def extract_key_information(self, paper: dict) -> dict:
        """
        Extract structured key information from a paper.
        Returns a dictionary with all configured summary sections.
        """
        paper_text = self._format_paper_for_prompt(paper)

        system = (
            f"{AGENT_INSTRUCTIONS['system_prompt']}\n\n"
            "Extract key information from research papers in a structured JSON-like format. "
            "Be precise and concise for each field."
        )

        user_msg = (
            f"Extract the following information from this paper. "
            f"Format each field on a new line as 'FIELD: value':\n\n"
            f"OBJECTIVES: (main research goals)\n"
            f"METHODOLOGY: (research approach/methods)\n"
            f"DATASETS: (datasets used)\n"
            f"MODELS: (models/algorithms used)\n"
            f"EXPERIMENTS: (experimental setup)\n"
            f"RESULTS: (key numerical results)\n"
            f"LIMITATIONS: (stated limitations)\n"
            f"FUTURE_WORK: (future directions mentioned)\n"
            f"CONTRIBUTIONS: (main contributions to the field)\n\n"
            f"Paper:\n{paper_text}"
        )

        prompt = self._build_prompt(system, user_msg)
        raw = self._call_model(prompt, max_tokens=800)

        # Parse the structured response
        result = {}
        for line in raw.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().upper()
                if key in ["OBJECTIVES", "METHODOLOGY", "DATASETS", "MODELS",
                           "EXPERIMENTS", "RESULTS", "LIMITATIONS",
                           "FUTURE_WORK", "CONTRIBUTIONS"]:
                    result[key.lower()] = value.strip()
        return result

    # ------------------------------------------------------------------
    # Helper — format paper dict into readable text for prompts
    # ------------------------------------------------------------------

    @staticmethod
    def _format_paper_for_prompt(paper: dict) -> str:
        """Convert a paper dict into a clean text block for LLM prompts."""
        authors = ", ".join(paper.get("authors", ["Unknown"])[:5])
        if len(paper.get("authors", [])) > 5:
            authors += " et al."

        lines = [
            f"Title: {paper.get('title', 'Unknown')}",
            f"Authors: {authors}",
            f"Year: {paper.get('year', 'n.d.')}",
            f"Source: {paper.get('source', 'Unknown')}",
        ]
        if paper.get("abstract"):
            lines.append(f"Abstract: {paper['abstract'][:800]}")
        if paper.get("keywords"):
            lines.append(f"Keywords: {', '.join(paper['keywords'][:10])}")
        if paper.get("doi"):
            lines.append(f"DOI: {paper['doi']}")

        return "\n".join(lines)
