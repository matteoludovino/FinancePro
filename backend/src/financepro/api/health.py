from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from financepro.db import get_db

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok"]


@router.get("/health")
def health(db: Annotated[Session, Depends(get_db)]) -> Health:
    # Touches the database, so the platform's health check fails when PostgreSQL is unreachable.
    db.execute(text("SELECT 1"))
    return Health(status="ok")
