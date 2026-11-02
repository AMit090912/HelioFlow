from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, dev, health, rules
from app.core.config import get_settings
from app.core.errors import error_response, install_error_handlers
from app.core.ratelimit import SlidingWindowLimiter

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="HelioFlow API", version="0.1.0")
    app.state.login_limiter = SlidingWindowLimiter(limit=5, window_seconds=60)
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
        else:
            response = await call_next(request)
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
    if settings.env != "production":
        app.include_router(dev.router, prefix="/api")
    return app


app = create_app()
