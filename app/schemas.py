from __future__ import annotations

from pydantic import BaseModel, Field


class PortableDocument(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=1_000_000)


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    documents: list[PortableDocument] = Field(default_factory=list, max_length=5)


class ChatRequest(RetrievalRequest):
    conversation_id: str | None = None
