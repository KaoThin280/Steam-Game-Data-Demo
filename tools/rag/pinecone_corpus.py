"""Standalone Documents API uploader. Does not change the chatbot or create indexes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def read_corpus(path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Corpus must be a nonempty JSON array")
    ids = set()
    for row in rows:
        for key in ("_id", "title", "text", "source", "status", "content_hash", "corpus_version"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"Missing field: {key}")
        if row["_id"] in ids:
            raise ValueError("Duplicate document ID")
        ids.add(row["_id"])
        if row["status"] != "approved":
            raise ValueError("Corpus contains unapproved content")
        if hashlib.sha256(row["text"].encode()).hexdigest() != row["content_hash"]:
            raise ValueError("Content hash mismatch; review changed content first")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "check", "dry-run", "upload", "verify", "search"])
    parser.add_argument("--env-file", type=Path, default=ROOT / "back_end/.env.docker.local")
    parser.add_argument("--corpus", type=Path, default=ROOT / "knowledge/project-starter.draft.json")
    parser.add_argument("--index", default="ai-data-knowledge")
    parser.add_argument("--namespace", default="project-starter-v2")
    parser.add_argument("--field", choices=["text", "chunk_text"], default="text")
    parser.add_argument("--query")
    parser.add_argument("--free-quota-checked", action="store_true", help="Confirm available free quota in Console before upload")
    args = parser.parse_args()
    rows = read_corpus(args.corpus)
    if any(r["corpus_version"] != args.namespace for r in rows):
        raise ValueError("Namespace must match corpus_version")
    if args.command == "validate":
        print(f"VALID: {len(rows)} approved articles; unique IDs and correct hashes")
        return
    if args.command in {"dry-run", "upload"}:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-large", trust_remote_code=False, cache_dir=ROOT / ".venv-rag/tokenizer-cache")
        lengths = [len(tokenizer.encode("passage: " + r["text"])) for r in rows]
        oversized = [r["_id"] for r, n in zip(rows, lengths) if n > 450]
        if oversized:
            raise ValueError("Split these articles before upload (450-token cap): " + ", ".join(oversized))
        print(json.dumps({"articles": len(rows), "max_tokens": max(lengths), "total_tokens": sum(lengths), "namespace": args.namespace}))
        if args.command == "dry-run":
            return
        if not args.free_quota_checked:
            raise ValueError("Check free quota in Console, then pass --free-quota-checked")
    from dotenv import dotenv_values
    from pinecone import Pinecone, EmbedQuery
    config = {**dotenv_values(args.env_file), **os.environ}
    key = config.get("PINECONE_API_KEY") or config.get("PINECORN_API_KEY")
    if not key:
        raise ValueError("Missing PINECONE_API_KEY or PINECORN_API_KEY")
    pc = Pinecone(api_key=key, timeout=15)
    description = pc.indexes.describe(args.index)
    # Print only selected public configuration, never credential or raw exception bodies.
    data = description.to_dict()
    schema = data.get("schema") or {}
    print(json.dumps({"index": args.index, "status": data.get("status"), "schema": schema}, ensure_ascii=False, default=str))
    if args.command == "check":
        return
    field = schema.get("fields", {}).get(args.field, {})
    if field.get("type") != "string" or (field.get("embed") or {}).get("model") != "multilingual-e5-large":
        raise ValueError("Expected a string field with multilingual-e5-large; check --field and index schema")
    index = pc.index(args.index)
    if args.command == "upload":
        docs = [dict(r) for r in rows]
        if args.field != "text":
            for doc in docs:
                doc[args.field] = doc.pop("text")
        for start in range(0, len(docs), 10):
            result = index.documents.upsert(namespace=args.namespace, documents=docs[start:start + 10])
            print(f"Accepted batch: {result.upserted_count} documents")
        print("Upload accepted. Run verify after indexing becomes visible; then search.")
    elif args.command == "verify":
        result = index.documents.fetch(namespace=args.namespace, ids=[r["_id"] for r in rows])
        documents = result.documents
        missing = [r["_id"] for r in rows if r["_id"] not in documents]
        if missing:
            raise ValueError("Not yet visible: " + ", ".join(missing))
        for row in rows:
            if documents[row["_id"]].get("content_hash") != row["content_hash"]:
                raise ValueError("Stored content hash differs from local corpus")
        print(f"VERIFIED: {len(rows)} IDs and hashes")
    elif args.command == "search":
        if not args.query or len(args.query) > 1000:
            raise ValueError("Supply --query with 1-1000 characters")
        result = index.documents.search(namespace=args.namespace, top_k=3, score_by=[EmbedQuery(field=args.field, query=args.query)], include_fields=["title", args.field, "source"])
        for doc in result.matches:
            print(json.dumps({"id": doc.id, "score": doc.score, "title": doc.get("title"), "text": doc.get(args.field), "source": doc.get("source")}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"STOP: {type(exc).__name__}. Check dependencies, connection, credentials and quota. Provider error body omitted to protect secrets.", file=sys.stderr)
        sys.exit(1)
