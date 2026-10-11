from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

from .rag import HybridRAG, citation_payload, extract_text, grounded_answer
from .schemas import ChatRequest, RetrievalRequest

app = FastAPI(title="Enterprise Autonomous Agentic RAG", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
rag = HybridRAG()
STATIC = Path(__file__).parent / "static" / "index.html"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
VERCEL_DEMO = os.getenv("RAG_DEPLOYMENT_MODE") == "vercel-demo"
MAX_VERCEL_UPLOAD_BYTES = 1_500_000


@app.get("/")
async def dashboard():
    return FileResponse(STATIC)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve a tiny SVG favicon, avoiding an otherwise harmless 404 in browser logs."""
    svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='14' fill='#1d4ed8'/><path d='M16 42 31 13l17 29h-9l-8-14-7 14z' fill='white'/></svg>"""
    return Response(svg, media_type="image/svg+xml")


@app.get("/health")
async def health():
    if VERCEL_DEMO:
        return {"status": "ok", "mode": "vercel-demo", "model_provider": "extractive fallback", "documents": 0, "child_chunks": 0, "parent_chunks": 0}
    return {"status": "ok", "mode": "local", "model": OLLAMA_MODEL, "model_provider": "ollama (optional)", **rag.status()}


@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        data = await file.read()
        if VERCEL_DEMO and len(data) > MAX_VERCEL_UPLOAD_BYTES:
            raise ValueError("Vercel demo files are limited to 1.5 MB.")
        filename = file.filename or "upload.txt"
        text = extract_text(filename, data)
        if not text.strip():
            raise ValueError("No extractable text was found in this file.")
        if VERCEL_DEMO:
            if len(text) > 1_000_000:
                raise ValueError("Extracted document text exceeds the 1,000,000 character demo limit.")
            preview = HybridRAG()
            result = preview.ingest(filename, text)
            return {**result, "portable_document": {"filename": filename, "text": text}, "storage": "browser-session"}
        return rag.ingest(filename, text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/v1/retrieval/inspect")
async def inspect_retrieval(request: RetrievalRequest):
    engine = request_engine(request.documents)
    results = engine.retrieve(request.query, request.top_k)
    relevance = max((item["rerank_score"] for item in results), default=0)
    return {"route": "hybrid_document_rag", "crag": "PASS" if relevance >= 0.2 else "REWRITE_RECOMMENDED", "results": results}


@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    engine = request_engine(request.documents)
    sources = engine.retrieve(request.query, request.top_k)
    relevance = max((item["rerank_score"] for item in sources), default=0)
    fallback_answer = grounded_answer(request.query, sources)

    async def model_answer() -> str | None:
        """Ask a local Ollama model, but never allow it to answer beyond retrieved evidence."""
        if VERCEL_DEMO or not sources:
            return None
        context = "\n\n".join(
            f"[^{number}] {source['filename']} (page {source['page']}):\n{source['text']}"
            for number, source in enumerate(sources, 1)
        )
        prompt = f"""You are a precise enterprise document assistant. Answer only from the evidence below.
Every factual sentence must include one or more citations in the exact form [^N].
If the evidence does not answer the question, say that clearly. Do not use outside knowledge.

Question: {request.query}

Evidence:
{context}
"""
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json={"model": OLLAMA_MODEL, "stream": False, "messages": [{"role": "user", "content": prompt}]},
                )
                response.raise_for_status()
                answer = response.json().get("message", {}).get("content", "").strip()
                # Reject answers without valid source markers: they cannot be verified.
                cited = [int(number) for number in re.findall(r"\[\^(\d+)\]", answer)]
                return answer if cited and all(1 <= number <= len(sources) for number in cited) else None
        except (httpx.HTTPError, ValueError):
            return None

    async def events():
        trace = [
            {"stage": "router", "message": "Classified request as hybrid document RAG."},
            {"stage": "retrieval", "message": f"Fused dense and BM25 rankings; selected {len(sources)} parent contexts."},
            {"stage": "crag", "message": "Evidence passed relevance threshold." if relevance >= 0.2 else "Evidence is weak; returning an abstention-safe answer."},
        ]
        for item in trace:
            yield f"event: trace\ndata: {json.dumps(item)}\n\n"
        generated = await model_answer()
        answer = generated or fallback_answer
        fallback_message = "Vercel demo uses extractive grounded generation." if VERCEL_DEMO else "Ollama unavailable or answer failed citation validation; using extractive grounded fallback."
        yield f"event: trace\ndata: {json.dumps({'stage': 'generation', 'message': f'Generated with local Ollama model {OLLAMA_MODEL}.' if generated else fallback_message})}\n\n"
        for word in answer.split(" "):
            yield f"event: token\ndata: {json.dumps({'text': word + ' '})}\n\n"
            await asyncio.sleep(0.012)
        yield f"event: citations\ndata: {json.dumps(citation_payload(sources))}\n\n"
        yield "event: done\ndata: {}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def request_engine(documents) -> HybridRAG:
    """Use browser-supplied documents on stateless Vercel; retain local in-memory behavior elsewhere."""
    if not documents:
        return rag
    engine = HybridRAG()
    for document in documents:
        engine.ingest(document.filename, document.text)
    return engine
