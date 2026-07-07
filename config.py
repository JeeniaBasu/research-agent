"""
=============================================================================
config.py — Application Configuration & Agent Instructions
=============================================================================
This module centralises all configuration for the AI Research Agent.
The AGENT_INSTRUCTIONS section at the bottom lets you customise the agent's
behaviour without touching any core application logic.
=============================================================================
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


# ---------------------------------------------------------------------------
# IBM Watsonx.ai Settings
# ---------------------------------------------------------------------------
class WatsonxConfig:
    API_KEY: str = os.getenv("IBM_CLOUD_API_KEY", "")
    PROJECT_ID: str = os.getenv("WATSONX_PROJECT_ID", "")
    URL: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

    # IBM Granite model identifiers
    CHAT_MODEL: str = "ibm/granite-8b-code-instruct"
    SUMMARIZER_MODEL: str = "ibm/granite-8b-code-instruct"
    REVIEW_MODEL: str = "ibm/granite-8b-code-instruct"

    # Generation parameters
    MAX_NEW_TOKENS: int = 2048
    TEMPERATURE: float = 0.3          # Lower = more factual, less creative
    TOP_P: float = 0.9
    REPETITION_PENALTY: float = 1.1


# ---------------------------------------------------------------------------
# Flask Settings
# ---------------------------------------------------------------------------
class FlaskConfig:
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("FLASK_PORT", 5000))


# ---------------------------------------------------------------------------
# Research API Settings
# ---------------------------------------------------------------------------
class ResearchConfig:
    SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    PUBMED_API_KEY: str = os.getenv("PUBMED_API_KEY", "")
    MAX_PAPERS_PER_SEARCH: int = int(os.getenv("MAX_PAPERS_PER_SEARCH", 10))

    # API Base URLs
    ARXIV_BASE_URL: str = "http://export.arxiv.org/api/query"
    SEMANTIC_SCHOLAR_BASE_URL: str = "https://api.semanticscholar.org/graph/v1"
    CROSSREF_BASE_URL: str = "https://api.crossref.org/works"
    PUBMED_SEARCH_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    PUBMED_FETCH_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    PUBMED_SUMMARY_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    # Request timeouts (seconds)
    REQUEST_TIMEOUT: int = 15
    MAX_RETRIES: int = 3


# ---------------------------------------------------------------------------
# Export Settings
# ---------------------------------------------------------------------------
class ExportConfig:
    EXPORT_DIR: str = os.getenv("EXPORT_DIR", "exports")
    MAX_HISTORY_ENTRIES: int = int(os.getenv("MAX_HISTORY_ENTRIES", 100))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# =============================================================================
# AGENT_INSTRUCTIONS
# =============================================================================
# Edit ONLY this section to customise the agent without touching any other file.
# Each key maps to a specific behaviour dimension of the Research Agent.
# =============================================================================

AGENT_INSTRUCTIONS = {

    # -------------------------------------------------------------------------
    # IDENTITY — Who the agent is
    # -------------------------------------------------------------------------
    "name": "ResearchMind",
    "version": "1.0.0",
    "description": (
        "An AI-powered academic research assistant built on IBM Granite, "
        "designed to help researchers discover, summarise, and synthesise "
        "scholarly literature with speed and precision."
    ),

    # -------------------------------------------------------------------------
    # DOMAIN EXPERTISE — Which research fields the agent specialises in
    # Supported: "general", "computer_science", "medicine", "physics",
    #            "biology", "chemistry", "social_sciences", "engineering"
    # -------------------------------------------------------------------------
    "domain_expertise": [
        "computer_science",
        "artificial_intelligence",
        "machine_learning",
        "data_science",
        "natural_language_processing",
    ],

    # -------------------------------------------------------------------------
    # RESPONSE TONE — Style of the agent's output
    # Options: "academic", "conversational", "concise", "detailed"
    # -------------------------------------------------------------------------
    "response_tone": "academic",

    # -------------------------------------------------------------------------
    # CITATION STYLE — Default citation format
    # Options: "APA", "IEEE", "MLA"
    # -------------------------------------------------------------------------
    "default_citation_style": "APA",

    # -------------------------------------------------------------------------
    # PREFERRED RESEARCH DATABASES — Order in which sources are queried
    # Options: "arxiv", "semantic_scholar", "crossref", "pubmed"
    # -------------------------------------------------------------------------
    "preferred_databases": ["arxiv", "semantic_scholar", "crossref", "pubmed"],

    # -------------------------------------------------------------------------
    # SUMMARY SETTINGS
    # -------------------------------------------------------------------------
    "summary_length": "medium",          # "short" | "medium" | "long"
    "summary_sections": [                # Sections to extract per paper
        "objectives",
        "methodology",
        "datasets",
        "models",
        "experiments",
        "results",
        "limitations",
        "future_work",
    ],

    # -------------------------------------------------------------------------
    # LITERATURE REVIEW SETTINGS
    # -------------------------------------------------------------------------
    "review_sections": [                 # Sections included in a lit review
        "introduction",
        "background",
        "thematic_analysis",
        "methodology_comparison",
        "results_synthesis",
        "research_gaps",
        "future_directions",
        "conclusion",
    ],
    "min_papers_for_review": 3,          # Minimum papers needed for a review
    "max_papers_for_review": 20,         # Maximum papers to synthesise

    # -------------------------------------------------------------------------
    # REPORT FORMAT — Sections to include in full research reports
    # -------------------------------------------------------------------------
    "report_sections": [
        "abstract",
        "introduction",
        "related_work",
        "methodology",
        "results",
        "discussion",
        "conclusion",
        "references",
    ],

    # -------------------------------------------------------------------------
    # SAFETY GUIDELINES
    # -------------------------------------------------------------------------
    "safety_guidelines": [
        "Never fabricate paper titles, authors, or DOIs.",
        "Always disclose uncertainty when information is incomplete.",
        "Do not generate misleading or unverified scientific claims.",
        "Recommend consulting original papers for critical decisions.",
        "Respect copyright: summarise content, never reproduce full papers.",
    ],

    # -------------------------------------------------------------------------
    # HALLUCINATION PREVENTION — RAG & grounding rules
    # -------------------------------------------------------------------------
    "hallucination_prevention": {
        "enabled": True,
        "rag_grounding": True,           # Ground answers in retrieved papers
        "cite_sources": True,            # Always cite sources in responses
        "confidence_threshold": 0.6,     # Min similarity score for RAG context
        "max_context_papers": 5,         # Papers injected into prompt context
        "unknown_response": (
            "I don't have sufficient information to answer that confidently. "
            "Please refine your query or consult the original papers directly."
        ),
    },

    # -------------------------------------------------------------------------
    # SYSTEM PROMPT — Master instruction injected before every LLM call
    # Modify this to globally change the agent's persona and constraints.
    # -------------------------------------------------------------------------
    "system_prompt": (
        "You are ResearchMind, an expert AI research assistant powered by IBM Granite. "
        "Your mission is to help researchers discover, understand, and synthesise "
        "academic literature with accuracy and depth.\n\n"
        "Core principles:\n"
        "1. ACCURACY: Ground every claim in retrieved papers. Never fabricate citations.\n"
        "2. CLARITY: Use clear, precise academic language appropriate for researchers.\n"
        "3. STRUCTURE: Always organise responses with headings and bullet points.\n"
        "4. TRANSPARENCY: State when you are uncertain or when data is unavailable.\n"
        "5. CITATION: Always attribute ideas and findings to their original sources.\n"
        "6. DEPTH: Provide substantive analysis, not superficial summaries.\n\n"
        "When summarising papers, always cover: objectives, methodology, key findings, "
        "limitations, and contributions to the field.\n"
        "When generating literature reviews, identify themes, contradictions, "
        "research gaps, and future directions.\n"
        "Format citations in the requested style (APA by default)."
    ),
}
