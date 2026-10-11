"""Vercel FastAPI entrypoint.

Vercel detects a root-level ``index.py`` exporting an ASGI ``app`` and
preserves the original request path for FastAPI routing.
"""

from app.main import app

