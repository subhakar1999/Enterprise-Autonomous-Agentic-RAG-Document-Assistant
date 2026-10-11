from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

WORD = re.compile(r"[A-Za-z0-9_\-/]+")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    id: str
    document_id: str
    filename: str
    page: int
    parent_id: str
    text: str
    kind: str = "child"


def tokens(text: str) -> list[str]:
    return [word.lower() for word in WORD.findall(text)]


def extract_sections(text: str) -> list[str]:
    """Keep Markdown headings and paragraph boundaries together where possible."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    sections, current = [], ""
    for block in blocks:
        if block.startswith("#") and current:
            sections.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}".strip()
    if current:
        sections.append(current)
    return sections


def windowed(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    output, start = [], 0
    while start < len(words):
        output.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
        start += size - overlap
    return output


class HybridRAG:
    """In-memory parent/child, hybrid retrieval engine suitable for local demos."""

    def __init__(self) -> None:
        self.children: dict[str, Chunk] = {}
        self.parents: dict[str, Chunk] = {}
        self.doc_ids: set[str] = set()
        self._tf: dict[str, Counter[str]] = {}
        self._df: Counter[str] = Counter()
        self._lengths: dict[str, int] = {}

    def ingest(self, filename: str, text: str, page: int = 1) -> dict:
        document_id = str(uuid.uuid4())
        child_count = 0
        for section_no, section in enumerate(extract_sections(text), 1):
            parent_id = f"{document_id}:p:{section_no}"
            parent_text = " ".join(windowed(section, 850, 100)) or section
            self.parents[parent_id] = Chunk(parent_id, document_id, filename, page, parent_id, parent_text, "parent")
            for child_no, child_text in enumerate(windowed(section, 180, 35), 1):
                child_id = f"{parent_id}:c:{child_no}"
                chunk = Chunk(child_id, document_id, filename, page, parent_id, child_text)
                self.children[child_id] = chunk
                tf = Counter(tokens(child_text))
                self._tf[child_id] = tf
                self._lengths[child_id] = sum(tf.values())
                self._df.update(tf.keys())
                child_count += 1
        self.doc_ids.add(document_id)
        return {"document_id": document_id, "filename": filename, "chunks_indexed": child_count}

    def _dense(self, query: str, limit: int) -> list[str]:
        # A deterministic hashing-vector encoder: fully local, no model download required.
        def vector(text: str) -> dict[int, float]:
            result: dict[int, float] = defaultdict(float)
            for word in tokens(text):
                result[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 384] += 1
            norm = math.sqrt(sum(v * v for v in result.values())) or 1
            return {k: v / norm for k, v in result.items()}
        q = vector(query)
        scored = []
        for cid, chunk in self.children.items():
            v = vector(chunk.text)
            scored.append((sum(q.get(k, 0) * value for k, value in v.items()), cid))
        return [cid for _, cid in sorted(scored, reverse=True)[:limit]]

    def _bm25(self, query: str, limit: int) -> list[str]:
        n = max(1, len(self.children))
        avgdl = sum(self._lengths.values()) / n if self._lengths else 1
        scored = []
        for cid, tf in self._tf.items():
            score = 0.0
            for term in tokens(query):
                if not tf[term]:
                    continue
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                score += idf * (tf[term] * 2.2) / (tf[term] + 1.2 * (1 - 0.75 + 0.75 * self._lengths[cid] / avgdl))
            scored.append((score, cid))
        return [cid for score, cid in sorted(scored, reverse=True)[:limit] if score > 0]

    @staticmethod
    def _rrf(*rankings: list[str], k: int = 60) -> list[tuple[str, float]]:
        scores: dict[str, float] = defaultdict(float)
        for ranking in rankings:
            for rank, cid in enumerate(ranking, 1):
                scores[cid] += 1 / (k + rank)
        return sorted(scores.items(), key=lambda row: row[1], reverse=True)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.children:
            return []
        dense, sparse = self._dense(query, 20), self._bm25(query, 20)
        query_terms = set(tokens(query))
        candidates = self._rrf(dense, sparse)
        # Lightweight cross-encoder proxy: reward joint exact-term coverage and phrase overlap.
        reranked = []
        for cid, rrf_score in candidates:
            text_terms = set(tokens(self.children[cid].text))
            coverage = len(query_terms & text_terms) / max(1, len(query_terms))
            reranked.append((0.65 * coverage + 0.35 * rrf_score * 60, cid, rrf_score))
        results = []
        used_parents = set()
        for score, cid, rrf_score in sorted(reranked, reverse=True):
            child = self.children[cid]
            if child.parent_id in used_parents:
                continue
            used_parents.add(child.parent_id)
            parent = self.parents[child.parent_id]
            results.append({"chunk_id": cid, "parent_id": parent.id, "document_id": child.document_id, "filename": child.filename, "page": child.page, "text": parent.text, "child_text": child.text, "rrf_score": round(rrf_score, 4), "rerank_score": round(score, 4)})
            if len(results) >= top_k:
                break
        return results

    def status(self) -> dict:
        return {"documents": len(self.doc_ids), "child_chunks": len(self.children), "parent_chunks": len(self.parents)}


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        import io
        return "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    if suffix not in {".txt", ".md", ".markdown"}:
        raise ValueError("Supported formats are PDF, TXT, and Markdown.")
    return data.decode("utf-8", errors="replace")


def grounded_answer(query: str, sources: list[dict]) -> str:
    if not sources:
        return "I couldn't find supporting information in the indexed documents. Upload relevant material or try a more specific question."
    # Deliberately extractive: no unsupported generative claims are introduced.
    terms = set(tokens(query))
    evidence = []
    for index, source in enumerate(sources, 1):
        sentences = SENTENCE.split(source["text"])
        best = max(sentences, key=lambda s: len(terms & set(tokens(s))), default=source["child_text"])
        evidence.append(f"{best.strip()} [^{index}]")
    return "\n\n".join(evidence)


def citation_payload(sources: list[dict]) -> list[dict]:
    return [{"number": i, "filename": s["filename"], "page": s["page"], "chunk_id": s["chunk_id"], "excerpt": s["child_text"][:360]} for i, s in enumerate(sources, 1)]
