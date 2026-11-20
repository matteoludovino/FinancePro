from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financepro.auth import limits, passwords, sessions
from financepro.auth.models import User
from financepro.auth.schemas import DeleteAccountIn, LoginIn, SignupIn, UserOut
from financepro.auth.sessions import CurrentUser
from financepro.categories import defaults
from financepro.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

DB = Annotated[Session, Depends(get_db)]
TOO_MANY = "Muitas tentativas. Espere alguns minutos e tente de novo."


def _spend_attempt(key: str | None = None) -> None:
    if limits.all_attempts.blocked("all") or (key is not None and limits.failed_by_email.blocked(key)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY)
    limits.all_attempts.hit("all")


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, db: DB, response: Response) -> UserOut:
    _spend_attempt()
    user = User(
        name=body.name, email=body.email.lower(), password_hash=passwords.hash_password(body.password)
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail.") from None
    defaults.seed(db, user.id)
    sessions.start(db, response, user)
    return UserOut.model_validate(user)


@router.post("/login")
def login(body: LoginIn, db: DB, response: Response) -> UserOut:
    key = body.email.lower()
    _spend_attempt(key)
    user = db.scalar(select(User).where(func.lower(User.email) == key))
    if not passwords.verify_password(user.password_hash if user else None, body.password) or user is None:
        limits.failed_by_email.hit(key)
        raise HTTPException(status_code=400, detail="E-mail ou senha incorretos.")
    limits.failed_by_email.clear(key)
    sessions.start(db, response, user)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DB) -> None:
    sessions.end(db, request, response)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: DeleteAccountIn, user: CurrentUser, request: Request, response: Response, db: DB
) -> None:
    """Deletes the user and, by cascade, everything they own (LGPD's right to deletion)."""
    if not user.is_sandbox:
        _spend_attempt(user.email)
        if not passwords.verify_password(user.password_hash, body.password or ""):
            limits.failed_by_email.hit(user.email)
            raise HTTPException(status_code=400, detail="Senha incorreta.")
    sessions.end(db, request, response)
    db.delete(user)
    db.commit()
