"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from codebase_historian.api.routers import router as v1_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Codebase Historian API",
        description="Multi-agent GraphRAG platform explaining codebase decisions, predicting blast radius, and suggesting reviewed refactors.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)

    @app.get("/")
    def root():
        return {
            "name": "Codebase Historian API",
            "version": "0.1.0",
            "docs": "/docs",
            "v1": "/v1",
        }

    return app


app = create_app()
