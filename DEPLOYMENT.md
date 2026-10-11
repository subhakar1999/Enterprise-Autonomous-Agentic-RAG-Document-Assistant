# Docker deployment

This stack runs the FastAPI dashboard and the local open-source Ollama model together. The first startup downloads `qwen2.5:1.5b`; this can take a few minutes and requires internet access only for that initial model download.

## Local Docker deployment

Install Docker Desktop, start it, then run from the repository root:

```powershell
docker compose up --build -d
docker compose logs -f
```

When `rag-assistant` reports that Uvicorn is running, open `http://localhost:8000`.

The model files live in Docker's `ollama-models` volume, so they are not downloaded again when containers restart.

## Useful operations

```powershell
# Check running containers
docker compose ps

# Rebuild the application after code changes
docker compose up --build -d

# Shut down without deleting the downloaded model
docker compose down
```

## Publish the API image

Replace `YOUR_DOCKERHUB_USER` with your Docker Hub namespace:

```powershell
docker tag enterprise-agentic-rag:latest YOUR_DOCKERHUB_USER/enterprise-agentic-rag:latest
docker login
docker push YOUR_DOCKERHUB_USER/enterprise-agentic-rag:latest
```

## Hosting choices

Deploy this Compose stack unchanged to a VM with Docker (AWS EC2, Azure VM, DigitalOcean Droplet, or a private server). A machine with at least 8 GB RAM is a sensible baseline for the API plus `qwen2.5:1.5b`; a GPU is optional but will improve generation speed.

For a production deployment, place a TLS reverse proxy such as Caddy or Nginx in front of port 8000 and use a DNS name. Do not expose Ollama port 11434 publicly.

## Current persistence boundary

The Ollama model is persistent via the Docker volume. Uploaded document chunks are held in the app's memory, so they reset when `rag-assistant` is recreated. Before a production rollout, replace the in-memory index with Qdrant (and persist source document metadata/object storage), matching the original architecture specification.
