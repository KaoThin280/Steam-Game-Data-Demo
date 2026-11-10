"""Prepare ignored credentials for the isolated local RAG demo, without remote DB URLs."""
import json
from pathlib import Path
import secrets

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
target = ROOT / "back_end/.env.rag-test.local"
if target.exists():
    print("Local fixture env already exists; left unchanged")
else:
    source = dotenv_values(ROOT / "back_end/.env.docker.local")
    values = {k: source[k] for k in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "PINECONE_API_KEY", "PINECORN_API_KEY") if source.get(k)}
    if not values.get("OPENROUTER_API_KEY") or not (values.get("PINECONE_API_KEY") or values.get("PINECORN_API_KEY")):
        raise SystemExit("Configure OpenRouter and Pinecone keys in .env.docker.local first")
    values.update(SECRET_KEY=secrets.token_hex(32), MCP_SHARED_SECRET=secrets.token_hex(32),
                  BOOTSTRAP_ADMIN_EMAIL="rag-local@example.com", BOOTSTRAP_ADMIN_PASSWORD=secrets.token_urlsafe(24))
    target.write_text("\n".join(k + "=" + json.dumps(v) for k, v in values.items()) + "\n", encoding="utf-8")
    print("Created ignored local env with provider keys and isolated test login; no remote DB/Redis URLs")
