"""
=============================================================================
app.py — AI-Powered Research Agent — Flask Application Entry Point
=============================================================================
Provides all REST API endpoints and serves the web frontend.
Built with Flask, IBM Watsonx.ai (Granite), RAG, and academic database APIs.

Endpoints:
  GET  /                       — Main chat interface
  GET  /dashboard              — Research analytics dashboard
  POST /api/chat               — Chat with the AI Research Agent
  POST /api/search             — Search research papers
  POST /api/summarize          — Summarize a single paper
  POST /api/compare            — Compare multiple papers
  POST /api/literature-review  — Generate a literature review
  POST /api/report-section     — Draft a report section
  POST /api/research-gaps      — Identify research gaps
  POST /api/citations          — Generate citations
  POST /api/export/pdf         — Export report as PDF
  POST /api/export/docx        — Export report as DOCX
  GET  /api/history            — Get search/chat history
  POST /api/history            — Save history entry
  DELETE /api/history/<id>     — Delete history entry
  GET  /api/bookmarks          — Get bookmarked papers
  POST /api/bookmarks          — Bookmark a paper
  DELETE /api/bookmarks/<id>   — Remove bookmark
  GET  /api/status             — Service health check
=============================================================================
"""

import json
import logging
import os
import uuid
from datetime import datetime
from functools import wraps
from io import BytesIO

import colorlog
from flask import (
    Flask, jsonify, request, render_template,
    send_file, session, abort
)
from flask_cors import CORS

from config import FlaskConfig, ExportConfig, AGENT_INSTRUCTIONS
from services.watsonx_service import WatsonxService
from services.research_service import ResearchService
from services.rag_service import RAGService
from utils.citation_utils import CitationManager
from utils.export_utils import ExportService

# =============================================================================
# Logging Configuration
# =============================================================================
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
))

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO"), logging.INFO),
    handlers=[handler],
)
logger = logging.getLogger(__name__)

# =============================================================================
# Flask Application Setup
# =============================================================================
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = FlaskConfig.SECRET_KEY
app.config["JSON_SORT_KEYS"] = False
CORS(app, resources={r"/api/*": {"origins": "*"}})

# =============================================================================
# Service Singletons
# =============================================================================
logger.info("🚀 Initialising ResearchMind AI Agent...")
watsonx = WatsonxService()
research = ResearchService()
rag = RAGService()
citations = CitationManager()
exporter = ExportService()

# In-memory storage (replace with a database in production)
_history: list = []     # [{ id, type, query, result, timestamp }]
_bookmarks: list = []   # [{ id, paper, bookmarked_at }]

# =============================================================================
# Helper Decorators & Utilities
# =============================================================================

def api_response(data: dict = None, message: str = "OK", status: int = 200):
    """Standardised JSON API response wrapper."""
    return jsonify({
        "success": status < 400,
        "message": message,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat(),
    }), status


def require_watsonx(f):
    """Decorator — returns 503 if Watsonx.ai is not initialised."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not watsonx.is_ready:
            return api_response(
                message=f"IBM Watsonx.ai is not available: {watsonx.init_error}",
                status=503
            )
        return f(*args, **kwargs)
    return decorated


def _save_history(entry_type: str, query: str, result: str, papers: list = None) -> dict:
    """Persist a history entry and return it."""
    entry = {
        "id": str(uuid.uuid4()),
        "type": entry_type,
        "query": query,
        "result": result,
        "papers": papers or [],
        "timestamp": datetime.utcnow().isoformat(),
    }
    _history.insert(0, entry)
    # Trim to max allowed entries
    while len(_history) > ExportConfig.MAX_HISTORY_ENTRIES:
        _history.pop()
    return entry


# =============================================================================
# Page Routes
# =============================================================================

@app.route("/")
def index():
    """Render the main chat interface."""
    return render_template(
        "index.html",
        agent_name=AGENT_INSTRUCTIONS["name"],
        watsonx_ready=watsonx.is_ready,
        watsonx_error=watsonx.init_error,
    )


@app.route("/dashboard")
def dashboard():
    """Render the research analytics dashboard."""
    stats = {
        "total_searches": len([h for h in _history if h["type"] == "search"]),
        "total_chats": len([h for h in _history if h["type"] == "chat"]),
        "total_summaries": len([h for h in _history if h["type"] == "summarize"]),
        "total_reviews": len([h for h in _history if h["type"] == "literature_review"]),
        "total_bookmarks": len(_bookmarks),
        "rag_documents": rag.document_count,
        "rag_papers": rag.paper_count,
    }
    return render_template(
        "dashboard.html",
        agent_name=AGENT_INSTRUCTIONS["name"],
        watsonx_ready=watsonx.is_ready,
        stats=stats,
        history=_history[:20],
        bookmarks=_bookmarks[:10],
    )


# =============================================================================
# API Routes
# =============================================================================

@app.route("/api/status")
def api_status():
    """Health check endpoint — returns service status."""
    return api_response(data={
        "agent": AGENT_INSTRUCTIONS["name"],
        "version": AGENT_INSTRUCTIONS["version"],
        "watsonx_ready": watsonx.is_ready,
        "watsonx_error": watsonx.init_error,
        "model": "ibm/granite-3-3-8b-instruct",
        "rag_papers": rag.paper_count,
        "history_entries": len(_history),
        "bookmarks": len(_bookmarks),
        "domain_expertise": AGENT_INSTRUCTIONS["domain_expertise"],
    })


# ------------------------------------------------------------------
# Chat
# ------------------------------------------------------------------

@app.route("/api/chat", methods=["POST"])
@require_watsonx
def api_chat():
    """
    Chat with the AI Research Agent.
    Supports conversation history and auto-retrieves relevant papers for RAG context.
    """
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    conversation_history = body.get("history", [])
    auto_search = body.get("auto_search", True)

    if not message:
        return api_response(message="Message is required.", status=400)

    logger.info("Chat: %s", message[:80])

    # Auto-retrieve papers for RAG context
    papers = []
    rag_context = ""
    if auto_search:
        try:
            papers = research.search(message, max_results=5)
            if papers:
                rag.index_papers(papers)
                rag_context = rag.build_context_string(message, papers)
                logger.info("RAG: injected context from %d papers", len(papers))
        except Exception as exc:
            logger.warning("Auto-search for RAG context failed: %s", exc)

    try:
        response_text = watsonx.chat(
            user_message=message,
            rag_context=rag_context,
            conversation_history=conversation_history,
        )
    except Exception as exc:
        logger.error("Chat LLM error: %s", exc)
        return api_response(message=str(exc), status=500)

    _save_history("chat", message, response_text, papers)

    return api_response(data={
        "response": response_text,
        "papers_used": len(papers),
        "rag_grounded": bool(rag_context),
        "papers": papers[:5],
    })


# ------------------------------------------------------------------
# Paper Search
# ------------------------------------------------------------------

@app.route("/api/search", methods=["POST"])
def api_search():
    """Search for research papers across configured academic databases."""
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    max_results = min(int(body.get("max_results", 10)), 20)
    databases = body.get("databases")  # Optional override

    if not query:
        return api_response(message="Search query is required.", status=400)

    logger.info("Search: '%s' (max=%d)", query[:80], max_results)

    try:
        papers = research.search(query, max_results=max_results, databases=databases)
        # Index papers into RAG store
        if papers:
            rag.index_papers(papers)
    except Exception as exc:
        logger.error("Search error: %s", exc)
        return api_response(message=f"Search failed: {exc}", status=500)

    _save_history("search", query, f"Found {len(papers)} papers", papers)

    return api_response(data={
        "query": query,
        "count": len(papers),
        "papers": papers,
    })


# ------------------------------------------------------------------
# Paper Summarizer
# ------------------------------------------------------------------

@app.route("/api/summarize", methods=["POST"])
@require_watsonx
def api_summarize():
    """Generate a structured summary of a single research paper."""
    body = request.get_json(silent=True) or {}
    paper = body.get("paper")
    detail_level = body.get("detail_level", AGENT_INSTRUCTIONS["summary_length"])

    if not paper:
        return api_response(message="Paper object is required.", status=400)

    logger.info("Summarize: %s", paper.get("title", "Unknown")[:80])

    try:
        summary = watsonx.summarize_paper(paper, detail_level=detail_level)
        key_info = watsonx.extract_key_information(paper)
    except Exception as exc:
        logger.error("Summarize error: %s", exc)
        return api_response(message=str(exc), status=500)

    _save_history("summarize", paper.get("title", "Unknown"), summary, [paper])

    return api_response(data={
        "paper": paper,
        "summary": summary,
        "key_information": key_info,
        "citations": citations.generate_all_styles(paper),
    })


# ------------------------------------------------------------------
# Paper Comparison
# ------------------------------------------------------------------

@app.route("/api/compare", methods=["POST"])
@require_watsonx
def api_compare():
    """Compare multiple research papers in structured tables."""
    body = request.get_json(silent=True) or {}
    papers = body.get("papers", [])

    if len(papers) < 2:
        return api_response(message="At least 2 papers are required for comparison.", status=400)

    logger.info("Compare: %d papers", len(papers))

    try:
        comparison = watsonx.compare_papers(papers)
    except Exception as exc:
        logger.error("Compare error: %s", exc)
        return api_response(message=str(exc), status=500)

    _save_history("compare", f"Comparison of {len(papers)} papers", comparison, papers)

    return api_response(data={
        "comparison": comparison,
        "paper_count": len(papers),
        "citations": {p.get("title", f"Paper {i}"): citations.apa(p)
                      for i, p in enumerate(papers, 1)},
    })


# ------------------------------------------------------------------
# Literature Review
# ------------------------------------------------------------------

@app.route("/api/literature-review", methods=["POST"])
@require_watsonx
def api_literature_review():
    """Generate a comprehensive academic literature review."""
    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    papers = body.get("papers", [])
    auto_search = body.get("auto_search", True)

    if not topic:
        return api_response(message="Research topic is required.", status=400)

    # Auto-search for papers if not provided
    if len(papers) < AGENT_INSTRUCTIONS["min_papers_for_review"] and auto_search:
        logger.info("Auto-searching papers for lit review: %s", topic)
        try:
            papers = research.search(topic, max_results=12)
            rag.index_papers(papers)
        except Exception as exc:
            logger.warning("Auto-search for lit review failed: %s", exc)

    if len(papers) < AGENT_INSTRUCTIONS["min_papers_for_review"]:
        return api_response(
            message=f"Not enough papers found. Need at least {AGENT_INSTRUCTIONS['min_papers_for_review']}.",
            status=400
        )

    logger.info("Literature review: '%s' with %d papers", topic[:80], len(papers))

    try:
        rag_context = rag.build_context_string(topic, papers)
        review = watsonx.generate_literature_review(papers, topic, rag_context)
        gaps = watsonx.suggest_research_gaps(papers, topic)
    except Exception as exc:
        logger.error("Literature review error: %s", exc)
        return api_response(message=str(exc), status=500)

    # Generate bibliography
    citation_style = AGENT_INSTRUCTIONS["default_citation_style"]
    bibliography = citations.generate_bibliography(papers, style=citation_style)

    _save_history("literature_review", topic, review, papers)

    return api_response(data={
        "topic": topic,
        "review": review,
        "research_gaps": gaps,
        "bibliography": bibliography,
        "paper_count": len(papers),
        "papers": papers,
    })


# ------------------------------------------------------------------
# Report Section Drafting
# ------------------------------------------------------------------

@app.route("/api/report-section", methods=["POST"])
@require_watsonx
def api_report_section():
    """Draft a specific section of a research paper."""
    body = request.get_json(silent=True) or {}
    section = (body.get("section") or "").strip()
    topic = (body.get("topic") or "").strip()
    notes = body.get("notes", "")
    papers = body.get("papers", [])

    if not section:
        return api_response(message="Section name is required.", status=400)
    if not topic:
        return api_response(message="Research topic is required.", status=400)

    allowed = AGENT_INSTRUCTIONS["report_sections"]
    if section.lower() not in [s.lower() for s in allowed]:
        return api_response(
            message=f"Unknown section. Allowed: {', '.join(allowed)}",
            status=400
        )

    logger.info("Report section: '%s' for topic '%s'", section, topic[:60])

    try:
        rag_context = rag.build_context_string(f"{topic} {section}", papers)
        content = watsonx.generate_report_section(
            section=section,
            context={"topic": topic, "notes": notes},
            papers=papers,
            rag_context=rag_context,
        )
    except Exception as exc:
        logger.error("Report section error: %s", exc)
        return api_response(message=str(exc), status=500)

    _save_history("report_section", f"{section}: {topic}", content, papers)

    return api_response(data={
        "section": section,
        "topic": topic,
        "content": content,
    })


# ------------------------------------------------------------------
# Research Gaps
# ------------------------------------------------------------------

@app.route("/api/research-gaps", methods=["POST"])
@require_watsonx
def api_research_gaps():
    """Identify research gaps, contradictions, and future directions."""
    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    papers = body.get("papers", [])

    if not topic:
        return api_response(message="Research topic is required.", status=400)

    if not papers:
        try:
            papers = research.search(topic, max_results=10)
            rag.index_papers(papers)
        except Exception as exc:
            logger.warning("Auto-search for gaps failed: %s", exc)

    logger.info("Research gaps: '%s' with %d papers", topic[:80], len(papers))

    try:
        gaps = watsonx.suggest_research_gaps(papers, topic)
    except Exception as exc:
        logger.error("Research gaps error: %s", exc)
        return api_response(message=str(exc), status=500)

    _save_history("research_gaps", topic, gaps, papers)

    return api_response(data={
        "topic": topic,
        "analysis": gaps,
        "papers_analyzed": len(papers),
    })


# ------------------------------------------------------------------
# Citations
# ------------------------------------------------------------------

@app.route("/api/citations", methods=["POST"])
def api_citations():
    """Generate citations for papers in APA, IEEE, or MLA format."""
    body = request.get_json(silent=True) or {}
    papers = body.get("papers", [])
    style = body.get("style", AGENT_INSTRUCTIONS["default_citation_style"]).upper()

    if not papers:
        return api_response(message="At least one paper is required.", status=400)

    if style not in CitationManager.SUPPORTED_STYLES:
        return api_response(
            message=f"Unsupported style. Use: {', '.join(CitationManager.SUPPORTED_STYLES)}",
            status=400
        )

    result = {}
    for paper in papers:
        title = paper.get("title", "Unknown")
        result[title] = {
            "paper": paper,
            "citation": citations.generate_citation(paper, style),
            "all_styles": citations.generate_all_styles(paper),
        }

    bibliography = citations.generate_bibliography(papers, style)

    return api_response(data={
        "style": style,
        "citations": result,
        "bibliography": bibliography,
    })


# ------------------------------------------------------------------
# Export: PDF
# ------------------------------------------------------------------

@app.route("/api/export/pdf", methods=["POST"])
def api_export_pdf():
    """Export a research report as a professional PDF document."""
    body = request.get_json(silent=True) or {}
    report = body.get("report")

    if not report:
        return api_response(message="Report data is required.", status=400)

    if not report.get("title"):
        report["title"] = f"Research Report — {report.get('topic', 'Unknown Topic')}"
    if not report.get("generated_at"):
        report["generated_at"] = datetime.now().strftime("%B %d, %Y at %H:%M UTC")

    logger.info("PDF export: %s", report.get("title", "Untitled"))

    try:
        pdf_buffer = exporter.export_pdf(report)
        filename = f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        logger.error("PDF export error: %s", exc)
        return api_response(message=f"PDF generation failed: {exc}", status=500)


# ------------------------------------------------------------------
# Export: DOCX
# ------------------------------------------------------------------

@app.route("/api/export/docx", methods=["POST"])
def api_export_docx():
    """Export a research report as a DOCX document."""
    body = request.get_json(silent=True) or {}
    report = body.get("report")

    if not report:
        return api_response(message="Report data is required.", status=400)

    if not report.get("title"):
        report["title"] = f"Research Report — {report.get('topic', 'Unknown Topic')}"
    if not report.get("generated_at"):
        report["generated_at"] = datetime.now().strftime("%B %d, %Y at %H:%M UTC")

    logger.info("DOCX export: %s", report.get("title", "Untitled"))

    try:
        docx_buffer = exporter.export_docx(report)
        filename = f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        return send_file(
            docx_buffer,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        logger.error("DOCX export error: %s", exc)
        return api_response(message=f"DOCX generation failed: {exc}", status=500)


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

@app.route("/api/history", methods=["GET"])
def api_get_history():
    """Retrieve research history entries."""
    entry_type = request.args.get("type")
    limit = min(int(request.args.get("limit", 50)), 100)

    filtered = _history
    if entry_type:
        filtered = [h for h in _history if h["type"] == entry_type]

    return api_response(data={
        "history": filtered[:limit],
        "total": len(filtered),
    })


@app.route("/api/history", methods=["POST"])
def api_save_history():
    """Manually save a history entry."""
    body = request.get_json(silent=True) or {}
    entry = _save_history(
        entry_type=body.get("type", "manual"),
        query=body.get("query", ""),
        result=body.get("result", ""),
        papers=body.get("papers", []),
    )
    return api_response(data={"entry": entry}, status=201)


@app.route("/api/history/<entry_id>", methods=["DELETE"])
def api_delete_history(entry_id: str):
    """Delete a history entry by ID."""
    global _history
    original_len = len(_history)
    _history = [h for h in _history if h["id"] != entry_id]
    if len(_history) == original_len:
        return api_response(message="History entry not found.", status=404)
    return api_response(message="History entry deleted.")


# ------------------------------------------------------------------
# Bookmarks
# ------------------------------------------------------------------

@app.route("/api/bookmarks", methods=["GET"])
def api_get_bookmarks():
    """Retrieve all bookmarked papers."""
    return api_response(data={
        "bookmarks": _bookmarks,
        "total": len(_bookmarks),
    })


@app.route("/api/bookmarks", methods=["POST"])
def api_add_bookmark():
    """Bookmark a paper."""
    body = request.get_json(silent=True) or {}
    paper = body.get("paper")

    if not paper:
        return api_response(message="Paper object is required.", status=400)

    # Check for duplicates
    paper_id = paper.get("id", "")
    if any(b["paper"].get("id") == paper_id for b in _bookmarks):
        return api_response(message="Paper is already bookmarked.", status=409)

    bookmark = {
        "id": str(uuid.uuid4()),
        "paper": paper,
        "bookmarked_at": datetime.utcnow().isoformat(),
        "citations": citations.generate_all_styles(paper),
    }
    _bookmarks.append(bookmark)

    return api_response(data={"bookmark": bookmark}, status=201)


@app.route("/api/bookmarks/<bookmark_id>", methods=["DELETE"])
def api_delete_bookmark(bookmark_id: str):
    """Remove a bookmark by ID."""
    global _bookmarks
    original_len = len(_bookmarks)
    _bookmarks = [b for b in _bookmarks if b["id"] != bookmark_id]
    if len(_bookmarks) == original_len:
        return api_response(message="Bookmark not found.", status=404)
    return api_response(message="Bookmark removed.")


# ------------------------------------------------------------------
# Follow-up Q&A
# ------------------------------------------------------------------

@app.route("/api/followup", methods=["POST"])
@require_watsonx
def api_followup():
    """Answer a follow-up question grounded in previously retrieved papers."""
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    papers = body.get("papers", [])

    if not question:
        return api_response(message="Question is required.", status=400)

    try:
        rag_context = rag.build_context_string(question, papers)
        answer = watsonx.answer_followup(question, papers, rag_context)
    except Exception as exc:
        logger.error("Followup error: %s", exc)
        return api_response(message=str(exc), status=500)

    _save_history("followup", question, answer, papers)

    return api_response(data={
        "question": question,
        "answer": answer,
        "papers_count": len(papers),
    })


# =============================================================================
# Error Handlers
# =============================================================================

@app.errorhandler(400)
def bad_request(e):
    return api_response(message="Bad request.", status=400)


@app.errorhandler(404)
def not_found(e):
    return api_response(message="Resource not found.", status=404)


@app.errorhandler(500)
def server_error(e):
    logger.error("Unhandled server error: %s", e)
    return api_response(message="Internal server error.", status=500)


# =============================================================================
# Application Entry Point
# =============================================================================

if __name__ == "__main__":
    os.makedirs(ExportConfig.EXPORT_DIR, exist_ok=True)
    logger.info("=" * 60)
    logger.info("  ResearchMind AI Agent — IBM Watsonx.ai")
    logger.info("  Model: ibm/granite-3-3-8b-instruct")
    logger.info("  Watsonx Ready: %s", watsonx.is_ready)
    if not watsonx.is_ready:
        logger.warning("  ⚠️  Configure .env with IBM credentials to enable AI features.")
    logger.info("=" * 60)

    app.run(
        host=FlaskConfig.HOST,
        port=FlaskConfig.PORT,
        debug=FlaskConfig.DEBUG,
    )
