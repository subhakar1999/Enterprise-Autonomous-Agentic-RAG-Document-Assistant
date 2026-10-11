<!-- STREAMING_CHUNK:Document header and executive overview -->
# Enterprise Autonomous Agentic RAG Document Assistant
## Architectural Blueprint & System Design Specification (AI Platform Engine)

---

## 1. Executive Summary & Engineering Mission

Most developer portfolios contain simplistic RAG implementations that do little more than load a PDF into LangChain's basic `CharacterTextSplitter`, store naive embeddings in an in-memory vector store, and dump top-3 chunks blindly into a chat completion prompt. In real-world enterprise environments, this naive approach fails across three critical dimensions:
1. **Semantic Drift & Irrelevant Retrieval:** Unranked semantic similarity frequently fetches topically adjacent but factually irrelevant text chunks, cluttering LLM context windows and increasing latency.
2. **Hallucination & Ungrounded Generation:** Generic prompting without strict citation verification allows LLMs to fabricate answers when retrieved documents contain only partial information.
3. **Rigid Query Processing:** Ambiguous, multi-part, or comparative queries ("Compare Q3 margins between 2023 and 2024") fail because standard vector lookups cannot break down multi-hop logical dependencies.

### What Makes This System Stand Out on LinkedIn, Resumes & Naukri:
* **Autonomous Agent Routing & Query Decomposition:** Analyzes query intent dynamically to determine whether to perform Direct Retrieval, Multi-Query Expansion, Sub-Query Decomposition, or Fallback Handling.
* **Hybrid Dense-Sparse Retrieval with Reciprocal Rank Fusion (RRF):** Combines dense vector semantic search (via Qdrant / ChromaDB) with sparse lexical search (BM25) to capture both semantic meaning and exact keyword hits (such as SKU codes, IDs, or exact phrases).
* **Cross-Encoder Reranking:** Applies high-precision cross-attention reranking (e.g., BGE-Reranker / FlashRank) to prune false positives before passing context to the LLM.
* **Corrective RAG (CRAG) & Self-Correction Loops:** An automated evaluator grades retrieved chunks for relevance. If document quality falls below threshold, the query is rewritten or directed to fallback paths.
* **Strict Citation Grounding & Guardrails:** Generates verifiable citation markers (`[^1]`, `[^2]`) linked to verified chunk IDs and source page offsets, rejecting ungrounded assumptions.
* **Production Asynchronous Streaming API:** Built on FastAPI with asynchronous streaming (Server-Sent Events / SSE), streaming both reasoning tokens ("Agent Thought Process") and synthesized answers.

---

<!-- STREAMING_CHUNK:High-level system topology and pipeline diagram -->
## 2. High-Level System Architecture

The platform operates as an asynchronous, agent-directed ingestion and inference engine:

```
                            [ User Document Ingestion ]
                                         │ (PDF / Markdown / TXT)
                                         ▼
                 ┌──────────────────────────────────────────────┐
                 │          Structure-Aware Ingestion           │
                 │  - Clean headers, tables, metadata           │
                 │  - Hierarchical / Parent-Child Chunking      │
                 └───────────────────────┬──────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
         Dense Embedding Pipeline                   Sparse BM25 Indexing
         (MiniLM / text-embedding-3)                (Lexical Inverted Index)
                    │                                         │
                    └────────────────────┬────────────────────┘
                                         ▼
                           Vector & Hybrid Store (Qdrant)
                           - Namespaced collections
                           - Rich metadata payloads

─────────────────────────────────────────────────────────────────────────────

                              [ User User Query ]
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │   Autonomous Agent Router │
                        │   - Intent Classification │
                        │   - Query Decomposition   │
                        │   - HyDE Query Expansion  │
                        └─────────────┬─────────────┘
                                      │
                                      ▼
                 ┌──────────────────────────────────────────┐
                 │       Hybrid Retrieval & RRF Fusion      │
                 │   Dense Vector Score + BM25 Lexical Rank │
                 └────────────────────┬─────────────────────┘
                                      │ Top 20 Candidates
                                      ▼
                 ┌──────────────────────────────────────────┐
                 │          Cross-Encoder Reranker          │
                 │          (FlashRank / BGE-Reranker)      │
                 └────────────────────┬─────────────────────┘
                                      │ Top 5 Reranked Chunks
                                      ▼
                 ┌──────────────────────────────────────────┐
                 │    CRAG Relevance Evaluator (Self-RAG)   │
                 └────────────────────┬─────────────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
                 ▼ [Score >= Threshold]                    ▼ [Score < Threshold]
      ┌─────────────────────────────┐           ┌─────────────────────────────┐
      │  Context Synthesis & SSE    │           │  Query Rewriting / Fallback │
      │  - Grounded answer stream   │           │  - Reformulate search terms │
      │  - Verifiable citation tags │           │  - Notify: No context found │
      │  - Hallucination guardrail  │           └─────────────────────────────┘
      └─────────────────────────────┘
```

---

<!-- STREAMING_CHUNK:Core technical components and decisions -->
## 3. Core Architectural Modules

### 3.1 Structure-Aware Ingestion & Parent-Child Chunking
* **The Problem:** Naive splitting of text into arbitrary 500-token chunks severs context mid-sentence and strips table headers, losing crucial relational data.
* **The Solution:** 
  * Parse documents with semantic awareness (respecting headings, code blocks, lists, and tables).
  * **Parent-Child Chunking:** Index small child chunks (128–256 tokens) for fine-grained vector similarity search. When a child chunk matches, retrieve the enclosing parent block (512–1024 tokens) to supply the LLM with complete semantic context.

### 3.2 Hybrid Search with Reciprocal Rank Fusion (RRF)
* **The Problem:** Vector embeddings can struggle with exact acronyms, part numbers, or rare technical terms. Conversely, keyword search misses synonyms and conceptual paraphrasing.
* **The Solution:** Execute both searches in parallel and fuse results using Reciprocal Rank Fusion:
  $$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  where $M = \{\text{Dense}, \text{Sparse}\}$, $k = 60$, and $r_m(d)$ is the rank of document $d$ in retrieval method $m$.

### 3.3 Cross-Encoder Reranking
* Bi-encoders (used during initial vector retrieval) compute embeddings for query and documents separately for speed.
* A Cross-Encoder processes query and candidate document jointly through transformer cross-attention layers, computing accurate relevance scores $\text{Score}(q, d) \in [0, 1]$.
* This prunes 20 candidate matches down to the 3–5 most factually relevant snippets.

### 3.4 Self-RAG & Corrective Feedback Loop (CRAG)
* Before passing context into generation, an evaluation step checks:
  1. *Are the retrieved documents actually relevant to the user query?*
  2. *Is key information missing?*
* If relevance is graded as `AMBIGUOUS` or `INCORRECT`, the system executes an automated query rewrite to try a different semantic angle, preventing hallucinations before generation begins.

### 3.5 Hallucination Verification & Citation Grounding
* The generation prompt enforces strict citation attribution:
  * Every statement of fact must reference an indexed chunk marker, e.g., `According to the Q3 financial statement [Doc: earnings_report.pdf, Page: 4, Chunk: 12]...`
* A verification pass flags any claims that lack direct textual grounding in the retrieved passages.

---

<!-- STREAMING_CHUNK:Tech stack definition and dependencies -->
## 4. Technology Stack Selection

| Component | Choice | Justification |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI (Python 3.11+)** | High-performance asynchronous runtime, native support for Server-Sent Events (SSE) streaming, and automatic OpenAPI schema generation. |
| **Vector Database** | **Qdrant (Embedded / Server)** | Ultra-fast Rust engine, native payload filtering, hybrid search capabilities, and local in-memory/file storage options. |
| **Sparse Lexical Engine** | **Rank-BM25 / FastBM25** | Standard BM25 lexical keyword scoring without external JVM/Elasticsearch infrastructure overhead. |
| **Reranking Engine** | **FlashRank / BGE-Reranker** | Ultra-lightweight, high-speed neural cross-encoder running efficiently on CPU or GPU. |
| **LLM & Embeddings** | **Google Gemini 3 / OpenAI / HuggingFace** | High-speed semantic embeddings and reasoning models with function calling and structured outputs. |
| **Document Processing** | **PyPDF / pdfplumber / Markdown-it** | Reliable document parsing, metadata extraction, and table preservation. |
| **Frontend UI** | **Modern Tailwind CSS + Vanilla JS Dashboard** | Clean, reactive interface with live document upload, vector chunk inspection, agent thought trace, and streaming chat. |

---

<!-- STREAMING_CHUNK:Phased implementation roadmap -->
## 5. Five-Phase Implementation Roadmap

### Phase 1: Ingestion Engine & Hybrid Vector Store
* Multi-format document parser (PDF, Markdown, Plain Text).
* Structure-aware parent-child text chunker with sliding overlap.
* Dual-index setup: Qdrant dense vector store + in-memory BM25 index.
* Fast ingestion API (`POST /api/v1/documents/upload`).

### Phase 2: Hybrid Retrieval & Cross-Encoder Reranker
* Reciprocal Rank Fusion (RRF) search pipeline.
* FlashRank / Cross-Encoder neural reranking stage.
* Retrieval inspection API (`POST /api/v1/retrieval/inspect`) returning ranked snippets with similarity scores.

### Phase 3: Autonomous Agent Router & Self-Correction (CRAG)
* Agent query analyzer: Direct Answer vs. Hybrid Document RAG vs. Multi-Query Expansion.
* Corrective RAG evaluation guardrail (checks relevance score threshold).
* Automatic query rewriting for ambiguous prompts.

### Phase 4: Token-Streaming Generation & Citation Grounding
* FastAPI Server-Sent Events (SSE) streaming endpoint (`POST /api/v1/chat/stream`).
* Inline verifiable citation tags (`[^1]`, `[^2]`) linked to source documents, page numbers, and chunk text.
* Hallucination guardrail validating output claims against retrieved text.

### Phase 5: Containerization, Testing & Portfolio Showcase
* Automated test suite (`pytest`) validating chunking, RRF fusion, reranker accuracy, and citation grounding.
* Multi-stage `Dockerfile` and `docker-compose.yml`.
* Recruiter-ready `README.md` with system diagrams and copy-paste resume bullet points.