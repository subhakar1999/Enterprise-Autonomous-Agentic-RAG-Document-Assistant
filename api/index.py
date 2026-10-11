"""Vercel Python Function entrypoint.

The rewrite in vercel.json forwards dashboard and API traffic to this FastAPI app.
"""

from app.main import app

