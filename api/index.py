"""
Vercel serverless entry. Python runtime expects an ASGI app exported as `app`.
See: https://vercel.com/docs/functions/runtimes/python
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mangum import Mangum

from main import app as fastapi_app

# Must be named `app` so Vercel registers this file as a Serverless Function.
app = Mangum(fastapi_app, lifespan="off")
