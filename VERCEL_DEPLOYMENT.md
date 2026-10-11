# Free Vercel demo deployment

This deployment contains only:

- The browser dashboard.
- The FastAPI serverless function.
- Small-file PDF, TXT, and Markdown parsing.
- Local hybrid retrieval and extractive, citation-grounded answers.

It does **not** deploy or call Ollama, Qdrant, Docker, or any paid/external model service. The existing Docker and Ollama files remain available for local development but are not part of the Vercel runtime.

## How the stateless demo works

After upload, extracted text is returned to the browser and kept in `sessionStorage`. The browser sends those small documents with retrieval and chat requests. This avoids relying on Vercel function memory, which can disappear between requests.

Session documents remain in the current browser tab and are removed when that tab/session is cleared. Nothing is persisted as a production knowledge base.

## Limits enforced by the app

- Maximum uploaded file size: 1.5 MB.
- Maximum extracted text per document: 1,000,000 characters.
- Maximum documents sent in one request: 5.
- Answers are extractive; no LLM is called.

These application limits leave room under Vercel's function request-size limits. Image-only/scanned PDFs require OCR and are not supported by this demo.

## Deploy from the Vercel dashboard

1. Push the repository to GitHub, GitLab, or Bitbucket.
2. In Vercel, select **Add New → Project** and import the repository.
3. Leave the framework and build settings at their defaults.
4. Deploy. No model keys or environment variables are required.
5. Open the generated `*.vercel.app` address, upload a small document, and ask a question.

`vercel.json` automatically sets `RAG_DEPLOYMENT_MODE=vercel-demo`, routing every request through the FastAPI entrypoint.

## Deploy with GitOps

Follow [GITOPS.md](GITOPS.md) to create preview deployments for pull requests and production deployments for changes merged to `main`.

## Local Docker mode is unchanged

Running `docker compose up --build -d` still starts the original FastAPI + Ollama stack. The Vercel-only behavior is activated solely by `RAG_DEPLOYMENT_MODE=vercel-demo`.
