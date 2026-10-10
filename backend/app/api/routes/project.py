import logging
from uuid import UUID
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Project
from app.models.conversation import Conversation
from app.schemas.db_schema import ProjectCreate, ProjectRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new FUSION project"
)
async def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    """Creates a new FUSION project session to associate conversations with."""
    try:
        project = Project(name=payload.name.strip())
        db.add(project)
        db.commit()
        db.refresh(project)
        logger.info(f"Created new project: {project.id} ('{project.name}')")
        return ProjectRead.model_validate(project)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to create project: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project session."
        )


@router.get(
    "",
    response_model=List[ProjectRead],
    summary="List all FUSION projects"
)
async def list_projects(db: Session = Depends(get_db)) -> List[ProjectRead]:
    """Retrieves all project sessions."""
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return [ProjectRead.model_validate(p) for p in projects]


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a project and all associated conversations from database"
)
async def delete_project(project_id: UUID, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Deletes a project from the database.
    Cascades deletion to all its conversations, extracted requirements, and summaries.
    """
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )

        db.delete(project)
        db.commit()
        logger.info(f"Successfully deleted project {project_id} and all its conversations from database.")
        return {
            "status": "success",
            "message": f"Project '{project_id}' and all associated conversations deleted from database.",
            "deleted_project_id": str(project_id)
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to delete project {project_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project from database: {str(exc)}"
        )


@router.delete(
    "/{project_id}/conversations",
    status_code=status.HTTP_200_OK,
    summary="Clear all conversations for a project from database"
)
async def delete_project_conversations(project_id: UUID, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Deletes all conversation records and extracted requirements for a project from the database,
    resetting the conversation turn count back to 0.
    """
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )

        deleted_count = db.query(Conversation).filter(Conversation.project_id == project_id).delete(synchronize_session=False)
        db.commit()
        logger.info(f"Deleted {deleted_count} conversations for project {project_id} from database.")
        return {
            "status": "success",
            "message": f"Cleared {deleted_count} conversations from database.",
            "project_id": str(project_id),
            "deleted_count": deleted_count
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to delete conversations for project {project_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear conversations from database."
        )


@router.post(
    "/new-session",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Delete old conversation/project from database and start a fresh new session"
)
async def start_new_session(
    old_project_id: Optional[UUID] = None,
    name: Optional[str] = "GeoAI Interactive Session",
    db: Session = Depends(get_db)
) -> ProjectRead:
    """
    Starts a fresh conversation session:
    1. If `old_project_id` is provided and exists, deletes it and all its conversations from the database.
    2. Creates and persists a brand new project session in the database.
    """
    try:
        if old_project_id:
            old_project = db.query(Project).filter(Project.id == old_project_id).first()
            if old_project:
                db.delete(old_project)
                logger.info(f"Deleted old project {old_project_id} from database before creating new session.")

        # Create new project session
        new_project = Project(name=name.strip() if name else "GeoAI Interactive Session")
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        logger.info(f"Started fresh session: {new_project.id} ('{new_project.name}')")
        return ProjectRead.model_validate(new_project)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to start new session: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start new conversation session."
        )
