import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from .agent.router import router as agent_router
from .chat.router import router as chat_router
from .integrations.router import router as integrations_router
from .database import create_db_and_tables, engine
from .rag.router import router as rag_router
from .routers import accounts, dashboard, employees, expenses, items, orders, partners, roles
from .seed import seed


def _wait_for_db(retries: int = 10, delay: float = 2.0) -> None:
    """DB 컨테이너가 아직 준비되지 않았을 때 잠시 재시도."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect():
                return
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wait_for_db()
    create_db_and_tables()
    if os.getenv("SEED_ON_START", "true").lower() == "true":
        seed()
    yield


app = FastAPI(title="제조 ERP 프로토타입 API", version="0.1.0", lifespan=lifespan)

# 프로토타입: 모든 오리진 허용 (본 개발 시 제한)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(items.router)
app.include_router(partners.router)
app.include_router(orders.router)
app.include_router(employees.router)
app.include_router(roles.router)
app.include_router(accounts.router)
app.include_router(expenses.router)
app.include_router(chat_router)
app.include_router(rag_router)
app.include_router(agent_router)
app.include_router(integrations_router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
