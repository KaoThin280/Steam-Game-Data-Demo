"""Pinecone Documents API adapter. No network or SDK initialization at startup."""
import json
from urllib.parse import urlparse

from app.agent_harness.knowledge import KnowledgeChunk, KnowledgeResult


class PineconeKnowledgeRetriever:
    def __init__(self, *, api_key: str, index_name: str, namespace: str, text_field: str = "text"):
        self.api_key = api_key
        self.index_name = index_name
        self.corpus_version = namespace
        self.text_field = text_field

    async def retrieve(self, query: str) -> KnowledgeResult:
        if not self.api_key:
            return KnowledgeResult("unavailable", self.corpus_version)
        from pinecone import AsyncPinecone, EmbedQuery, RetryConfig

        async with AsyncPinecone(api_key=self.api_key, timeout=5, retry_config=RetryConfig(max_retries=0)) as client:
            async with await client.index(self.index_name) as index:
                result = await index.documents.search(
                    namespace=self.corpus_version, top_k=5,
                    filter={"status": {"$eq": "approved"}, "corpus_version": {"$eq": self.corpus_version}},
                    score_by=[EmbedQuery(field=self.text_field, query=query)],
                    include_fields=["title", self.text_field, "source", "status", "corpus_version"],
                )
        return self.normalize(result.matches)

    def normalize(self, matches) -> KnowledgeResult:
        chunks, seen = [], set()
        # Conservative UTF-8 byte budget for serialized evidence (<=1800 byte-level
        # tokens). No tokenizer/model downloads on the request path; keep whole articles.
        used = 0
        for doc in matches[:5]:
            if doc.get("status") != "approved" or doc.get("corpus_version") != self.corpus_version:
                continue
            text, title, source = (doc.get(k) for k in (self.text_field, "title", "source"))
            if not all(isinstance(v, str) and v.strip() for v in (text, title, source)):
                continue
            if text in seen:
                continue
            parsed = urlparse(source)
            # External source links are HTTPS only. Internal paths are labels, not links.
            if parsed.scheme and (parsed.scheme != "https" or not parsed.netloc):
                continue
            chunk = KnowledgeChunk(str(doc.id), title, text, source, f"S{len(chunks) + 1}")
            from dataclasses import asdict
            cost = len(json.dumps(asdict(chunk), ensure_ascii=False).encode("utf-8"))
            if used + cost > 1600:  # reserve 200 bytes for envelope
                continue
            chunks.append(chunk)
            seen.add(text)
            used += cost
        return KnowledgeResult("ok" if chunks else "empty", self.corpus_version, tuple(chunks))
