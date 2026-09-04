"""Independent Steam MCP-compatible JSON-RPC server.

Run separately from the API:
    uvicorn app.mcp_server:app --host 127.0.0.1 --port 8001
"""
import hmac

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.agent_harness.mcp import MockSteamMCPServer
from app.core.config import settings
from app.db.session import close_db, readonly_engine
from sqlalchemy import text


class JSONRPCRequest(BaseModel):
    jsonrpc: str = Field(pattern=r"^2\.0$")
    id: str | int
    method: str
    params: dict = Field(default_factory=dict)


app = FastAPI(title="Steam Data MCP Server", version="1.0.0")
server = MockSteamMCPServer()


def _authorize(authorization: str | None) -> None:
    expected = settings.MCP_SHARED_SECRET
    if not expected and settings.DEBUG:
        return
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid MCP service credential")


@app.get("/health")
async def health():
    async with readonly_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "healthy", "transport": "http-jsonrpc"}


@app.post("/mcp")
async def mcp(request: JSONRPCRequest, authorization: str | None = Header(None)):
    _authorize(authorization)
    return await server.handle(request.model_dump())


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db()
