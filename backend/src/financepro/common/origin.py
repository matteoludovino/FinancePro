"""Cross-site request forgery: state-changing requests must come from the web app's own pages.

The session cookie is SameSite=Lax, which already keeps it off cross-site POSTs in current browsers.
This check is the second layer, and the one that covers `multipart/form-data` uploads: a form on any
site can send one without a CORS preflight. Browsers always send `Origin` on POST/PUT/PATCH/DELETE and
`Sec-Fetch-Site` on every request; a client that sends neither isn't a browser, so it holds no victim's
cookie, and is let through (tests, curl).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from financepro.settings import get_settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def is_trusted(request: Request, web_origin: str) -> bool:
    if request.method in SAFE_METHODS:
        return True
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site")
    if origin is not None:
        return origin == web_origin
    return fetch_site in (None, "same-origin")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def check_origin(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not is_trusted(request, get_settings().web_origin):
            return JSONResponse(status_code=403, content={"detail": "Origem da requisição não permitida."})
        return await call_next(request)
