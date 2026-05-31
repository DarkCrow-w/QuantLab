from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quant.config import get_settings
from server.routers import backtest, market, screening, strategy

try:
    from server.agent.router import router as agent_router
    from server.agent.model import get_agent_runtime_status
    AGENT_IMPORT_ERROR: str | None = None
except Exception as e:
    agent_router = None
    get_agent_runtime_status = None
    AGENT_IMPORT_ERROR = str(e)

app = FastAPI(title="量化回测平台 API", version="0.1.0")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.app.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtest.router)
app.include_router(strategy.router)
app.include_router(market.router)
app.include_router(screening.router)
if agent_router is not None:
    app.include_router(agent_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/agent/status")
def agent_status():
    if agent_router is None:
        return {
            "enabled": False,
            "reason": AGENT_IMPORT_ERROR or "agent dependencies unavailable",
            "hint": "Install pyproject Agent dependencies: langchain, langchain-anthropic, langgraph, langgraph-supervisor.",
        }
    return get_agent_runtime_status()
