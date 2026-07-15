"""
FastAPI Backend for Research Society Agent System.
Provides REST API and WebSocket for real-time agent chat, mapping, and fact-checking.
"""

import json
import logging
import os
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

# --- Input size / rate-limit constants (consolidated to avoid magic numbers) ---
MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB upper bound for /paper/upload file size
MAX_SECTION_TEXT_BYTES = 200_000  # cap total paper sections per request
MAX_IDENTIFIER_LENGTH = 2_000
MAX_QUERY_LENGTH = 1_000
MAX_GOAL_LENGTH = 2_000
DEBATE_RESULT_TTL_SECONDS = 600

# Rate limiting constants ( requests per minute )
RATE_LIMIT_WINDOW_MINUTES = 1
RATE_LIMIT_MAX_REQUESTS = 60  # 60 requests per minute (1 per second average)

_ALLOWED_UPLOAD_DIRS = (
    Path(tempfile.gettempdir()).resolve(),
    Path(os.getenv("RESEARCH_SOCIETY_UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))).resolve(),
)


from config import settings
from paper_ingest.parser import parse_pdf
from paper_ingest.fetcher import PaperFetcher
from agents.base import AgentFactory, AgentMessage
from agents.executive_moderator import ExecutiveModerator
from debate.manager import DebateManager
from debate.benchmark import compare_reviews
from mapping.map_generator import ConceptMapGenerator
from fact_check.checker import FactChecker

logger = logging.getLogger(__name__)


# Pydantic models for API
class PaperIdentifier(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=MAX_IDENTIFIER_LENGTH)

    @field_validator("identifier")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("identifier cannot be empty")
        return v


class PaperDiscoverRequest(BaseModel):
    request: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH, description="What kind of papers you want, in plain English")
    max_results: int = Field(default=8, ge=1, le=20)
    expand_query: bool = Field(default=True, description="Use LLM to expand into better search queries")


class PaperQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH, description="Natural language: research goal, URL, DOI, or paper title")
    max_results: int = Field(default=8, ge=1, le=20)
    expand_query: bool = Field(default=True)


class PDFUpload(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=4096)

    @field_validator("file_path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("file_path cannot be empty")
        # Refuse obviously dangerous paths early (URLs, null bytes)
        if v.startswith("http://") or v.startswith("https://"):
            raise ValueError("file_path must be a local path, not a URL")
        if "\x00" in v:
            raise ValueError("file_path cannot contain null bytes")
        # Sanitize: remove leading/trailing whitespace and control chars
        return v.strip()


class DebateConfig(BaseModel):
    max_rounds: int = Field(default_factory=lambda: settings.MAX_ROUNDS, ge=1, le=20)
    min_rounds: int = Field(default=3, ge=1, le=20)
    crossfire_passes: int = Field(default=2, ge=0, le=10)
    consensus_threshold: float = Field(
        default_factory=lambda: settings.CONSENSUS_THRESHOLD,
        ge=0.0,
        le=1.0,
    )


class GenerateMapRequest(BaseModel):
    paper_title: str = Field(..., min_length=1, max_length=500, description="Title of the paper")
    sections: Dict[str, str] = Field(..., description="Paper sections")

    @field_validator("sections")
    @classmethod
    def _sections_size(cls, v: Dict[str, str]) -> Dict[str, str]:
        total = sum(len(c or "") for c in v.values())
        if total > MAX_SECTION_TEXT_BYTES:
            raise ValueError(
                f"sections exceed {MAX_SECTION_TEXT_BYTES} chars total "
                f"(got {total})"
            )
        return v


class VerifyClaimsRequest(BaseModel):
    sections: Dict[str, str] = Field(..., description="Paper sections")
    max_claims: int = Field(default=10, ge=1, le=50)

    @field_validator("sections")
    @classmethod
    def _sections_size(cls, v: Dict[str, str]) -> Dict[str, str]:
        total = sum(len(c or "") for c in v.values())
        if total > MAX_SECTION_TEXT_BYTES:
            raise ValueError(
                f"sections exceed {MAX_SECTION_TEXT_BYTES} chars total "
                f"(got {total})"
            )
        return v


class PaperResponse(BaseModel):
    success: bool
    paper_id: str
    type: str
    title: Optional[str] = None
    authors: List[str] = []
    abstract: str = ""
    categories: List[str] = []
    sections: Dict[str, str] = {}
    error_message: Optional[str] = None
    hint: Optional[str] = None


class DebateStartRequest(BaseModel):
    paper_id: str = Field(..., min_length=1, max_length=500)
    paper_title: str = Field(..., min_length=1, max_length=500)
    sections: Dict[str, str] = Field(...)
    config: Optional[DebateConfig] = None

    @field_validator("sections")
    @classmethod
    def _sections_size(cls, v: Dict[str, str]) -> Dict[str, str]:
        total = sum(len(c or "") for c in v.values())
        if total > MAX_SECTION_TEXT_BYTES:
            raise ValueError(
                f"sections exceed {MAX_SECTION_TEXT_BYTES} chars total "
                f"(got {total})"
            )
        return v


class BenchmarkRequest(BaseModel):
    paper_title: str = Field(..., min_length=1, max_length=500)
    sections: Dict[str, str] = Field(...)
    society_report: str = Field(..., min_length=1, max_length=200_000)
    society_messages: Optional[List[str]] = None

    @field_validator("sections")
    @classmethod
    def _sections_size(cls, v: Dict[str, str]) -> Dict[str, str]:
        total = sum(len(c or "") for c in v.values())
        if total > MAX_SECTION_TEXT_BYTES:
            raise ValueError(
                f"sections exceed {MAX_SECTION_TEXT_BYTES} chars total "
                f"(got {total})"
            )
        return v

    @field_validator("society_messages")
    @classmethod
    def _limit_messages(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        if len(v) > 500:
            raise ValueError("society_messages too long (max 500 entries)")
        return v


class PlanRequest(BaseModel):
    paper_title: str = Field(..., min_length=1, max_length=500)
    sections: Dict[str, str] = Field(...)

    @field_validator("sections")
    @classmethod
    def _sections_size(cls, v: Dict[str, str]) -> Dict[str, str]:
        total = sum(len(c or "") for c in v.values())
        if total > MAX_SECTION_TEXT_BYTES:
            raise ValueError(
                f"sections exceed {MAX_SECTION_TEXT_BYTES} chars total "
                f"(got {total})"
            )
        return v


class TopicResearchRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=MAX_GOAL_LENGTH, description="What you are trying to learn or accomplish")
    max_discover: int = Field(default=8, ge=3, le=15)
    papers_to_debate: int = Field(default=3, ge=1, le=5)
    top_recommendations: int = Field(default=3, ge=1, le=5)
    expand_query: bool = True
    debate_config: Optional[DebateConfig] = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.debate_in_progress: bool = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, data: dict):
        message = json.dumps(data)
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Research Society starting...")
    yield
    print("Research Society shutting down...")


app = FastAPI(title="Research Society API", version="2.0.0", lifespan=lifespan)

# CORS — wildcard origin with credentials disabled is acceptable for dev.
# For production, configure explicit origins and enable CORS credentials properly.
# This is a research app where the UI may be served from different hosts during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak stack traces or internal error strings to API consumers."""
    # Log the full trace server-side, return a sanitized message to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

connection_manager = ConnectionManager()
api_router = APIRouter(prefix="/api")


@api_router.get("/health")
def health_check():
    from config import (
        has_cloud_api_key,
        is_using_dashscope,
        settings as cfg,
    )

    configured = has_cloud_api_key() or "localhost" in cfg.API_BASE_URL
    return {
        "status": "healthy" if configured else "degraded",
        "model": cfg.MODEL_NAME,
        "api_base_url": cfg.API_BASE_URL,
        "api_key_configured": has_cloud_api_key(),
        "using_dashscope": is_using_dashscope(),
        "version": "2.0.0",
    }


@api_router.post("/paper/identify")
async def identify_paper_endpoint(request: PaperIdentifier) -> PaperResponse:
    try:
        fetcher = PaperFetcher()
        paper_type, metadata = fetcher.identify_paper(request.identifier)

        if not metadata or not metadata.title:
            return PaperResponse(
                success=False,
                paper_id=request.identifier,
                type=paper_type,
            )

        return PaperResponse(
            success=True,
            paper_id=metadata.paper_id,
            type=paper_type,
            title=metadata.title,
            authors=metadata.authors,
            abstract=metadata.abstract[:500] if metadata.abstract else "",
            categories=metadata.categories,
        )
    except Exception as e:
        # Log details server-side; do not echo internal exception text to the client
        logger.exception("paper/identify failed for %r", request.identifier)
        raise HTTPException(status_code=502, detail="Could not identify paper from this identifier")


@api_router.post("/paper/fetch-full")
async def fetch_full_paper_endpoint(request: PaperIdentifier) -> PaperResponse:
    """Identify a paper and extract section content for downstream agents."""
    try:
        fetcher = PaperFetcher()
        paper_type, metadata = fetcher.identify_paper(request.identifier)

        if not metadata or not metadata.title:
            hint = None
            if request.identifier.startswith("http") and "jamanetwork.com" in request.identifier:
                hint = (
                    "JAMA blocks automated access. Copy the DOI from the article page "
                    "(e.g. 10.1001/jamaneurol.2023.3889) or paste the doi.org link."
                )
            elif request.identifier.startswith("http"):
                hint = "Try pasting the paper's DOI, PubMed link, or a title search instead."
            return PaperResponse(
                success=False,
                paper_id=request.identifier,
                type=paper_type,
                error_message="Could not resolve paper from this identifier.",
                hint=hint,
            )

        sections = fetcher.extract_sections_from_metadata(metadata, paper_type)

        return PaperResponse(
            success=True,
            paper_id=metadata.paper_id,
            type=paper_type,
            title=metadata.title,
            authors=metadata.authors,
            abstract=metadata.abstract[:500] if metadata.abstract else "",
            categories=metadata.categories,
            sections=sections,
        )
    except Exception as e:
        logger.exception("paper/fetch-full failed for %r", request.identifier)
        raise HTTPException(status_code=502, detail="Could not fetch paper details")


@api_router.post("/paper/discover")
async def discover_papers_endpoint(request: PaperDiscoverRequest):
    """
    Find papers on the open scholarly web from a natural-language research goal.
    Searches OpenAlex, PubMed, and arXiv — then you load one for debate/analysis.
    """
    from paper_ingest.discovery import discover_from_request

    try:
        if not request.request.strip():
            raise HTTPException(status_code=400, detail="Research request cannot be empty")

        result = await discover_from_request(
            request.request.strip(),
            max_results=request.max_results,
            use_llm_expansion=request.expand_query,
        )
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception:
        logger.exception("paper/discover failed")
        raise HTTPException(status_code=502, detail="Paper discovery failed")


@api_router.post("/paper/query")
async def paper_query_endpoint(request: PaperQueryRequest):
    """
    Natural-language entry point: paste a URL/DOI or describe papers you want.
    Auto-routes to direct load or scholarly web discovery.
    """
    from paper_ingest.query import handle_paper_query

    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        return await handle_paper_query(
            request.query.strip(),
            max_results=request.max_results,
            expand_query=request.expand_query,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("paper/query failed")
        raise HTTPException(status_code=502, detail="Paper query failed")


@api_router.post("/research/topic")
async def research_topic_endpoint(request: TopicResearchRequest):
    """
    Discover papers for a research goal, run agent-society debate on each,
    and return ranked recommendations.
    """
    from research.topic_ranker import research_topic

    if connection_manager.debate_in_progress:
        raise HTTPException(status_code=409, detail="A debate or topic research run is already in progress")

    connection_manager.debate_in_progress = True

    try:
        debate_config = None
        if request.debate_config:
            debate_config = request.debate_config.model_dump()

        result = await research_topic(
            user_goal=request.goal.strip(),
            max_discover=request.max_discover,
            papers_to_debate=request.papers_to_debate,
            top_recommendations=request.top_recommendations,
            expand_query=request.expand_query,
            debate_config=debate_config,
            on_event=_broadcast_event,
        )
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("research/topic failed")
        raise HTTPException(status_code=502, detail="Topic research failed")
    finally:
        connection_manager.debate_in_progress = False


@api_router.post("/paper/upload")
async def upload_paper(request: PDFUpload) -> PaperResponse:
    """Upload a local PDF file for processing. Validates path is within allowed directories."""
    # Validate the file path is safe
    try:
        resolved_path = Path(request.file_path).resolve()
        
        # Check if path is in allowed directories (path traversal protection)
        path_in_allowed = False
        for allowed_dir in _ALLOWED_UPLOAD_DIRS:
            try:
                resolved_path.relative_to(allowed_dir)
                path_in_allowed = True
                break
            except ValueError:
                continue
        
        if not path_in_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"File path must be within allowed directories: {list(str(d) for d in _ALLOWED_UPLOAD_DIRS)}"
            )
        
        # Additional check: path must exist and be a file
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        if not os.path.isfile(request.file_path):
            raise HTTPException(status_code=400, detail="Path is not a file")
            
    except Exception as e:
        logger.exception("path validation failed for %r", request.file_path)
        raise HTTPException(status_code=400, detail=f"Invalid file path: {e}")

    try:
        paper = parse_pdf(request.file_path)
        sections = {}
        for key in ("abstract", "introduction", "methodology", "results", "discussion", "conclusion"):
            content = getattr(paper, key, "") or ""
            if content.strip():
                sections[key] = content.strip()

        return PaperResponse(
            success=True,
            paper_id=os.path.basename(request.file_path),
            type="pdf",
            title=paper.title or "Unknown Title",
            authors=paper.authors,
            abstract=paper.abstract[:500] if paper.abstract else "",
            sections=sections,
        )
    except Exception as e:
        logger.exception("paper/upload failed for %r", request.file_path)
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {e}")


async def _broadcast_agent_message(msg: AgentMessage, round_num: int):
    await connection_manager.broadcast_json({
        "type": "agent_message",
        "agent_id": msg.agent_id,
        "agent_name": msg.agent_name,
        "role": msg.role,
        "content": msg.content,
        "turn": msg.turn,
        "round_num": round_num,
        "message_type": msg.message_type,
        "stance": msg.stance,
        "confidence": msg.confidence,
        "evidence": msg.evidence,
    })


async def _broadcast_event(event: dict):
    await connection_manager.broadcast_json(event)


@api_router.post("/debate/start")
async def start_debate(request: DebateStartRequest):
    if connection_manager.debate_in_progress:
        raise HTTPException(status_code=409, detail="Debate already in progress")

    connection_manager.debate_in_progress = True

    try:
        await connection_manager.broadcast_json({
            "type": "debate_started",
            "paper_title": request.paper_title,
        })

        moderator = ExecutiveModerator()
        agents = [
            AgentFactory.create_agent("structure_analyst"),
            AgentFactory.create_agent("contribution_scout"),
            AgentFactory.create_agent("methodology_critic"),
            AgentFactory.create_agent("literature_reviewer"),
        ]

        config = request.config or DebateConfig()
        manager = DebateManager(
            moderator=moderator,
            agents=agents,
            max_rounds=config.max_rounds,
            min_rounds=config.min_rounds,
            crossfire_passes=config.crossfire_passes,
            consensus_threshold=config.consensus_threshold,
            on_message=_broadcast_agent_message,
            on_event=_broadcast_event,
        )

        session = await manager.initialize_session(
            paper_summary=f"Paper: {request.paper_title}",
            sections=request.sections,
        )

        result = await manager.run_debate(session)

        society_messages = [m.content for r in result.rounds for m in r.messages]

        await connection_manager.broadcast_json({
            "type": "debate_complete",
            "rounds_completed": len(result.rounds),
            "final_report": result.final_report,
            "verdict": result.verdict,
            "dissent_ledger": result.dissent_ledger,
            "assignments": [a.to_dict() for a in result.task_assignments],
            "agreement_history": result.agreement_history,
        })

        return {
            "success": True,
            "paper_id": request.paper_id,
            "rounds_completed": len(result.rounds),
            "final_report": result.final_report,
            "verdict": result.verdict,
            "dissent_ledger": result.dissent_ledger,
            "assignments": [a.to_dict() for a in result.task_assignments],
            "agreement_history": result.agreement_history,
            "messages": [
                {
                    "agent_id": m.agent_id,
                    "agent_name": m.agent_name,
                    "role": m.role,
                    "content": m.content,
                    "turn": m.turn,
                    "message_type": m.message_type,
                    "stance": m.stance,
                    "confidence": m.confidence,
                    "evidence": m.evidence,
                    "round_num": r.round_number,
                }
                for r in result.rounds
                for m in r.messages
            ],
        }
    finally:
        connection_manager.debate_in_progress = False


@api_router.get("/debate/status")
def get_debate_status():
    return {
        "in_progress": connection_manager.debate_in_progress,
        "active_connections": len(connection_manager.active_connections),
    }


@api_router.post("/debate/plan")
async def plan_debate(request: PlanRequest):
    """Preview task decomposition without running full debate."""
    from agents.base import AgentContext

    moderator = ExecutiveModerator()
    agents = [
        AgentFactory.create_agent("structure_analyst"),
        AgentFactory.create_agent("contribution_scout"),
        AgentFactory.create_agent("methodology_critic"),
        AgentFactory.create_agent("literature_reviewer"),
    ]
    ctx = AgentContext()
    moderator.set_context(ctx)
    ctx.update_paper_context(f"Paper: {request.paper_title}", request.sections)

    assignments = await moderator.decompose_tasks(
        f"Paper: {request.paper_title}",
        request.sections,
        agents,
    )
    return {"assignments": [a.to_dict() for a in assignments]}


@api_router.post("/benchmark/compare")
async def benchmark_compare(request: BenchmarkRequest):
    """Compare multi-agent society output vs single-agent solo reviewer."""
    if not request.society_report:
        raise HTTPException(status_code=400, detail="society_report required (run debate first)")

    try:
        result = await compare_reviews(
            request.paper_title,
            request.sections,
            request.society_report,
            request.society_messages,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/map/generate")
async def generate_map(request: GenerateMapRequest):
    if not request.sections:
        raise HTTPException(status_code=400, detail="No paper sections provided")

    generator = ConceptMapGenerator()
    await generator.generate_map(request.sections, paper_title=request.paper_title)

    return {
        "paper_title": request.paper_title,
        "map": generator.to_json(),
        "svg": generator.to_svg(),
        "central_concept": generator.central_concept,
        "summary": generator.summary,
        "key_points": generator.key_points,
        "takeaways": generator.takeaways,
    }


@api_router.post("/fact-check/verify")
async def verify_claims(request: VerifyClaimsRequest):
    checker = FactChecker()
    results = await checker.verify_all_claims(request.sections, request.max_claims)

    return {
        "paper_sections_analyzed": len(request.sections),
        "claims_verified": sum(1 for r in results if r.is_verified),
        "total_claims": len(results),
        "results": [
            {
                "claim_id": r.claim_id,
                "claim_text": r.claim,
                "is_verified": r.is_verified,
                "confidence": r.confidence,
                "cross_references": r.cross_references,
            }
            for r in results
        ],
    }


app.include_router(api_router)

FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST_PATH", "")).resolve()
if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/")
def read_root():
    if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    return {
        "name": "Research Society API",
        "version": "2.0.0",
        "description": "Multi-agent debate system for scientific paper analysis",
        "api_prefix": "/api",
    }


if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").exists():

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api") or full_path.startswith("ws"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await connection_manager.connect(websocket)

    try:
        await websocket.send_json({
            "type": "welcome",
            "message": "Connected to Research Society debate stream",
        })

        while True:
            data = await websocket.receive_text()
            print(f"WebSocket received: {data}")

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        print("Client disconnected")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
