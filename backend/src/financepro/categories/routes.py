from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from financepro.auth.sessions import CurrentUser
from financepro.categories import service
from financepro.categories.schemas import CategoryIn, CategoryOut, CategoryPatch
from financepro.db import get_db

router = APIRouter(prefix="/categories", tags=["categories"])

DB = Annotated[Session, Depends(get_db)]


@router.get("")
def list_categories(user: CurrentUser, db: DB) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in service.list_categories(db, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, user: CurrentUser, db: DB) -> CategoryOut:
    return CategoryOut.model_validate(service.create_category(db, user.id, body))


@router.patch("/{category_id}")
def update_category(category_id: int, body: CategoryPatch, user: CurrentUser, db: DB) -> CategoryOut:
    return CategoryOut.model_validate(service.update_category(db, user.id, category_id, body))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, user: CurrentUser, db: DB) -> None:
    service.delete_category(db, user.id, category_id)
