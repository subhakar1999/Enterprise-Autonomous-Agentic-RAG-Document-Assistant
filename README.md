# Enterprise Autonomous Agentic RAG Document Assistant

A runnable portfolio implementation of an enterprise document assistant. It ingests PDF, TXT, and Markdown documents, finds grounded evidence, and answers with verifiable citations.

## What problem it solves

Basic “chat with PDF” applications often retrieve text that is only loosely related to a question, then let an LLM generate an unverified answer. That is unreliable for policies, reports, technical documents, and internal knowledge bases.

| Problem | Resolution in this app |
| --- | --- |
| Text is split mid-thought and loses context | Parent-child chunking finds precise child chunks, then returns their larger parent context. |
| Semantic search misses IDs, SKUs, acronyms, and exact wording | Hybrid retrieval combines dense-style retrieval with BM25 keyword search. |
| High-similarity chunks may still be irrelevant | Reciprocal Rank Fusion combines both result lists and a reranking stage prioritizes the strongest evidence. |
| A model may invent an answer when evidence is incomplete | CRAG-style relevance gating marks weak results; the app returns a safe, evidence-based fallback. |
| Answers are difficult to audit | Answers use `[^1]` citation markers tied to the source filename, page, and indexed chunk. |
| Cloud model costs or privacy are a concern | Optional Ollama generation runs `qwen2.5:1.5b` locally, without an API key. |
| Users cannot see why an answer was returned | The UI streams routing, retrieval, relevance, and generation trace events. |

For example, for “Compare Q3 margins for 2023 and 2024,” the app retrieves evidence for both years, ranks it, and requires citations. If the uploaded documents do not contain enough evidence for the comparison, it should not make the comparison up.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Upload a PDF, TXT, or Markdown file, then ask a question. See [USER_GUIDE.md](USER_GUIDE.md) for step-by-step use.

## Lightweight open-source model (recommended)

The app uses a local Ollama model when it is available. Install [Ollama](https://ollama.com/), then run:

```powershell
ollama pull qwen2.5:1.5b
ollama serve
```

`qwen2.5:1.5b` is a capable lightweight model for a laptop. It avoids any cloud API key. The app will automatically call it at `http://127.0.0.1:11434`; if the service is off, it safely falls back to extractive, citation-grounded answers.

Choose another installed Ollama model with:

```powershell
$env:OLLAMA_MODEL = "phi3:mini"
uvicorn app.main:app --reload
```

## API

- `POST /api/v1/documents/upload` — multipart field `file`
- `POST /api/v1/retrieval/inspect` — `{ "query": "...", "top_k": 5 }`
- `POST /api/v1/chat/stream` — Server-Sent Events, returns trace, tokens, and citations
- `GET /health` — index status

## Current MVP boundaries

- The document index is held in memory and resets when the application container is recreated.
- The model persists in the Docker `ollama-models` volume.
- The default embedding and reranking components are deterministic local implementations, so the demo runs without API keys or model downloads.
- For production, use Qdrant for durable vector storage, preserve source documents in object storage, and replace the lightweight reranker with FlashRank or BGE.

## Deployment

- Docker deployment with local Ollama: [DEPLOYMENT.md](DEPLOYMENT.md)
- Free Vercel dashboard/API demo using browser-session documents and extractive answers: [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md)
- GitHub Actions GitOps pipeline for preview and production deployments: [GITOPS.md](GITOPS.md)

## Tests

```powershell
pytest
```
