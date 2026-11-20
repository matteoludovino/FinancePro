from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financepro.categories.models import Category
from financepro.categories.schemas import CategoryIn, CategoryPatch
from financepro.categorization.models import Rule

DUPLICATE = "Já existe uma categoria com este nome aqui."


def list_categories(db: Session, owner_id: int) -> list[Category]:
    query = select(Category).where(Category.owner_id == owner_id).order_by(Category.type, Category.name)
    return list(db.scalars(query))


def get_category(db: Session, owner_id: int, category_id: int) -> Category:
    category = db.scalar(select(Category).where(Category.id == category_id, Category.owner_id == owner_id))
    if category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    return category


def _save(db: Session, category: Category) -> Category:
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE) from None
    db.commit()
    return category


def create_category(db: Session, owner_id: int, data: CategoryIn) -> Category:
    if data.parent_id is not None:
        parent = get_category(db, owner_id, data.parent_id)
        if parent.parent_id is not None:
            raise HTTPException(status_code=422, detail="Subcategorias não podem ter subcategorias.")
        category = Category(owner_id=owner_id, parent_id=parent.id, name=data.name, type=parent.type)
    elif data.type is None:
        raise HTTPException(status_code=422, detail="Diga se é uma categoria de gasto ou de receita.")
    else:
        category = Category(owner_id=owner_id, name=data.name, type=data.type)
    db.add(category)
    return _save(db, category)


def update_category(db: Session, owner_id: int, category_id: int, data: CategoryPatch) -> Category:
    category = get_category(db, owner_id, category_id)
    if data.name is not None:
        category.name = data.name
    if data.is_archived is not None:
        category.is_archived = data.is_archived
    return _save(db, category)


def delete_category(db: Session, owner_id: int, category_id: int) -> None:
    category = get_category(db, owner_id, category_id)
    children = db.scalar(select(func.count()).where(Category.parent_id == category.id))
    if children:
        raise HTTPException(status_code=409, detail="Exclua ou arquive as subcategorias antes.")
    rules = db.scalar(select(func.count()).where(Rule.category_id == category.id))
    if rules:
        message = f"{rules} regra(s) usam esta categoria. Mude ou exclua as regras, ou arquive a categoria."
        raise HTTPException(status_code=409, detail=message)
    db.delete(category)
    db.commit()
