"""Vercel serverless entrypoint for the booking backend.

Vercel's Python runtime serves the module-level `app` (an ASGI app). We add the
parent dir (booking/) to sys.path so we can import the real FastAPI app from
main.py without duplicating it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402,F401  (re-exported for Vercel)
