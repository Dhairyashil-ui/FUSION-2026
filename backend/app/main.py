from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import verify_database_connection, init_db
from app.schemas.db_schema import HealthResponse
from app.api.routes.test_groq import router as test_groq_router
from app.api.routes.query import router as query_router
from app.api.routes.project import router as project_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.jobs import router as jobs_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="FUSION 2026 - User Query Understanding and Information Collection System",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(test_groq_router, prefix=settings.API_V1_PREFIX)
app.include_router(query_router, prefix=settings.API_V1_PREFIX)
app.include_router(project_router, prefix=settings.API_V1_PREFIX)
app.include_router(retrieval_router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def on_startup():
    init_db()


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "phase": "User Query Understanding and Information Collection System"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Simple application health status endpoint."""
    return {"status": "ok"}


@app.get("/health/database", tags=["Health"])
async def health_database():
    """Verifies PostgreSQL database connection and PostGIS availability."""
    result = verify_database_connection()
    if result.get("status") == "ok":
        return result
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=result
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
