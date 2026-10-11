from app.rag import HybridRAG, grounded_answer


def test_hybrid_retrieval_returns_parent_context():
    rag = HybridRAG()
    rag.ingest("report.md", "# Revenue\n\nThe Q3 margin increased to 24 percent. Revenue rose due to enterprise sales.")
    result = rag.retrieve("What was the Q3 margin?")
    assert result
    assert "24 percent" in result[0]["text"]


def test_grounded_answer_abstains_without_evidence():
    assert "couldn't find" in grounded_answer("Anything?", [])
