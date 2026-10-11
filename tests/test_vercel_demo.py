import os

os.environ["RAG_DEPLOYMENT_MODE"] = "vercel-demo"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_vercel_demo_is_stateless_and_extractive():
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("report.txt", b"The Q3 margin increased to 24 percent.", "text/plain")},
    )
    assert upload.status_code == 200
    portable = upload.json()["portable_document"]

    inspection = client.post(
        "/api/v1/retrieval/inspect",
        json={"query": "What was the Q3 margin?", "documents": [portable]},
    )
    assert inspection.status_code == 200
    assert inspection.json()["results"]
    assert "24 percent" in inspection.json()["results"][0]["text"]

    response = client.post(
        "/api/v1/chat/stream",
        json={"query": "What was the Q3 margin?", "documents": [portable]},
    )
    assert response.status_code == 200
    assert "24 percent" in response.text
    assert "Vercel demo uses extractive grounded generation" in response.text
