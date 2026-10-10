import logging
from typing import Dict, Any, Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.config import settings

logger = logging.getLogger(__name__)

# Base class for SQLAlchemy models
Base = declarative_base()

# Engine and Session initialization
engine = None
SessionLocal = None


def get_database_url() -> Optional[str]:
    """Retrieve and normalize DATABASE_URL for SQLAlchemy."""
    url = settings.DATABASE_URL
    if not url:
        return "sqlite:///./fusion_2026.db"
    # Normalize postgres/postgresql prefix to postgresql+psycopg2:// driver explicitly
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def create_app_engine():
    """Initializes and returns the SQLAlchemy engine."""
    url = get_database_url()
    if not url:
        return None

    if "sqlite" in url.lower():
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG
        )
    else:
        return create_engine(
            url,
            pool_pre_ping=True,
            echo=settings.DEBUG
        )


engine = create_app_engine()
if engine is not None:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes tables for all registered models."""
    global engine
    if engine is None:
        engine = create_app_engine()
        if engine is not None:
            global SessionLocal
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    if engine is not None:
        # Import models so Base.metadata knows about all tables
        import app.models.project  # noqa: F401
        import app.models.conversation  # noqa: F401
        import app.models.extracted_requirement  # noqa: F401
        import app.models.conversation_summary  # noqa: F401

        Base.metadata.create_all(bind=engine)
        logger.info("FUSION 2026 database tables verified and created successfully.")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    if SessionLocal is None:
        init_db()
    if SessionLocal is None:
        raise RuntimeError("Database engine is not initialized. Check DATABASE_URL.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_database_connection() -> Dict[str, Any]:
    """
    Verifies database connection and checks status.
    
    Returns:
        dict: Status information including database connectivity, dialect, and Supabase config.
    """
    url = get_database_url()
    if not url:
        return {
            "status": "error",
            "database": "disconnected",
            "message": "DATABASE_URL is not configured."
        }

    current_engine = engine
    if current_engine is None:
        current_engine = create_app_engine()

    try:
        with current_engine.connect() as conn:
            conn.execute(text("SELECT 1;"))

            is_sqlite = "sqlite" in url.lower()
            response: Dict[str, Any] = {
                "status": "ok",
                "database": "connected",
                "type": "sqlite" if is_sqlite else "postgresql",
                "supabase_url": settings.SUPABASE_URL,
                "supabase_ready": bool(settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY)
            }

            if not is_sqlite:
                postgis_check = conn.execute(
                    text("SELECT extname FROM pg_extension WHERE extname = 'postgis';")
                ).scalar()
                if postgis_check:
                    response["postgis"] = "enabled"

            return response

    except Exception as exc:
        logger.error(f"Database connection verification failed: {exc}")
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(exc)
        }
