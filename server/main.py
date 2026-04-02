from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routers import backtest, market, screening, strategy
# from server.agent.router import router as agent_router  # 暂时禁用，等依赖安装完成

app = FastAPI(title="量化回测平台 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtest.router)
app.include_router(strategy.router)
app.include_router(market.router)
app.include_router(screening.router)
# app.include_router(agent_router)  # 暂时禁用


@app.get("/api/health")
def health():
    return {"status": "ok"}
