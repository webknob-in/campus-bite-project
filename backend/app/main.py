from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, health, owner_menu, restaurants
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware

API_TITLE = "CampusBite API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
REST API for **CampusBite**, a campus food-ordering platform with three roles:
**CUSTOMER**, **RESTAURANT_OWNER**, and **DELIVERY_PARTNER**.

* Authenticate with `POST /auth/login`, then send `Authorization: Bearer <access_token>`.
* Every error response is JSON with a `detail` field.
* List endpoints accept `page` (>= 1) and `page_size` (1-100) and return
  `{items, total, page, page_size}`.
* Payments are simulated (dummy card form); no real charge is made.
"""

# One entry per router; routers declare ``tags=[<name>]`` so /docs and /redoc group them.
OPENAPI_TAGS = [
    {"name": "auth", "description": "Registration, login, and the current user's profile."},
    {"name": "restaurants", "description": "Public restaurant, menu, dish search, and review browsing."},
    {"name": "orders", "description": "Customer orders: place, history, detail, cancel, review, and return."},
    {"name": "owner-menu", "description": "Restaurant owner menu management."},
    {"name": "owner-orders", "description": "Restaurant owner order management and delivery partner assignment."},
    {"name": "owner-returns", "description": "Restaurant owner return and refund decisions."},
    {"name": "owner-insights", "description": "Restaurant statistics and delayed-order reminders."},
    {"name": "partner", "description": "Delivery partner assigned orders, status updates, and history."},
    {"name": "ai", "description": "AI-powered order insights from the caller's own order history."},
    {"name": "health", "description": "Service and database health check."},
]


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()  # fail fast at startup when DATABASE_URL or JWT_SECRET is missing (Req 39.6)
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    register_exception_handlers(app)

    # The last middleware added is the outermost. CORS must wrap RequestContext so the
    # 500 that RequestContext builds for an unhandled exception still gets CORS headers
    # (otherwise a browser reports a CORS error instead of the 500).
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Process-Time", "X-Request-ID", "Retry-After"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(restaurants.router)
    app.include_router(owner_menu.router)
    return app


app = create_app()
