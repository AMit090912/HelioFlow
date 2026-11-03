import logging
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, bills, dev, health, leads, projects, public, quotes, rules, staff
from app.core import logging as redaction
from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.core.errors import error_response, install_error_handlers
from app.core.ratelimit import SlidingWindowLimiter
from app.services.ai import GeminiProvider, GroqProvider, Provider
from app.services.ai.demo import SAMPLE_FINGERPRINTS, DemoProvider


def providers_for(settings: Settings):
    """Provider chain per upload (ARCHITECTURE §6.5): live Groq → Gemini, or none in tests (where
    fakes are injected). Demo mode answers only for the synthetic sample bill; a real bill goes to
    the live chain when keys are set, otherwise straight to manual entry. Demo never tells a
    person their real bill "isn't a bill"."""
    if settings.ai_mode == "test":
        return lambda sha: []
    chain: list[Provider] = []
    if settings.groq_api_key:
        chain.append(
            GroqProvider(
                settings.groq_api_key,
                settings.groq_vision_model,
                settings.groq_text_model,
                timeout=settings.ai_timeout_seconds,
            )
        )
    if settings.gemini_api_key:
        chain.append(
            GeminiProvider(
                settings.gemini_api_key, settings.gemini_model, timeout=settings.ai_timeout_seconds
            )
        )
    if settings.ai_mode == "demo":
        return lambda sha: [DemoProvider(sha)] if sha in SAMPLE_FINGERPRINTS else chain
    if not chain:
        logging.getLogger("helio.ai").warning(
            "AI_MODE=live but no GROQ_API_KEY or GEMINI_API_KEY: every bill will need manual entry"
        )
    return lambda sha: chain


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_UPLOAD_PATH = re.compile(r"^/api/leads/[^/]+/bills$")
_MULTIPART_OVERHEAD = 256 * 1024


def _oversized_upload(request: Request, max_mb: int):
    """Refuse an oversized bill upload from its Content-Length, before the multipart parser
    receives (and spools) the whole body (§5.1)."""
    if request.method != "POST" or not _UPLOAD_PATH.match(request.url.path):
        return None
    length = request.headers.get("content-length")
    if length is None:
        return error_response(411, "LENGTH_REQUIRED", "Upload size is required.")
    if not length.isdigit() or int(length) > max_mb * 1024 * 1024 + _MULTIPART_OVERHEAD:
        return error_response(413, "FILE_TOO_LARGE", f"This file is larger than {max_mb} MB.")
    return None


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def create_app() -> FastAPI:
    settings = get_settings()
    redaction.install()
    app = FastAPI(title="HelioFlow API", version="0.1.0")
    app.state.login_limiter = SlidingWindowLimiter(limit=5, window_seconds=60)
    app.state.upload_limiter = SlidingWindowLimiter(limit=10, window_seconds=3600)
    app.state.status_limiter = SlidingWindowLimiter(limit=30, window_seconds=60)  # §4
    # Background bill reading gets its own session and provider chain; tests swap both.
    app.state.session_factory = SessionLocal
    app.state.ai_providers = providers_for(settings)
    install_error_handlers(app)

    @app.middleware("http")
    async def csrf_and_headers(request: Request, call_next):
        # A cross-site form cannot set custom headers, so this blocks CSRF (§4).
        if (
            request.method in UNSAFE_METHODS
            and request.url.path.startswith("/api/")
            and request.headers.get("x-hf-csrf") != "1"
        ):
            response = error_response(403, "CSRF_HEADER_MISSING", "Missing request header.")
        elif (too_big := _oversized_upload(request, settings.max_upload_mb)) is not None:
            response = too_big
        else:
            response = await call_next(request)
        if request.url.path.startswith("/api/public/"):
            # Status links are secrets in the URL: never leak them onward or into search (§12).
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
            response.headers["Cache-Control"] = "no-store"
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    # Normal traffic is same-origin via the Next.js rewrite; CORS only admits the frontend.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-HF-CSRF"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(rules.router, prefix="/api")
    app.include_router(bills.router, prefix="/api")
    app.include_router(leads.router, prefix="/api")
    app.include_router(staff.router, prefix="/api")
    app.include_router(quotes.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(public.router, prefix="/api")
    if settings.env != "production":
        app.include_router(dev.router, prefix="/api")
    return app


app = create_app()
