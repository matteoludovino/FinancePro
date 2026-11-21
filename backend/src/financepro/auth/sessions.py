import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from financepro import clock
from financepro.auth.models import Session as SessionRow
from financepro.auth.models import User
from financepro.db import get_db
from financepro.settings import get_settings

TTL = timedelta(days=14)
# Demo sandboxes live while used: 3 hours idle and they are gone (docs/adr/0007).
SANDBOX_TTL = timedelta(hours=3)


def _ttl(user: User) -> timedelta:
    return SANDBOX_TTL if user.is_sandbox else TTL


def _extend_after(user: User) -> timedelta:
    # A session in use is extended, but rarely: at most once a day (every 10 minutes for a sandbox).
    return timedelta(minutes=10) if user.is_sandbox else timedelta(days=1)


def cookie_name() -> str:
    # The __Host- prefix makes the browser refuse the cookie unless it is Secure, Path=/ and has no
    # Domain: a sibling subdomain can't plant or read it. It needs HTTPS, so only in production.
    return "__Host-fp_session" if get_settings().production else "fp_session"


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _set_cookie(response: Response, token: str, ttl: timedelta) -> None:
    response.set_cookie(
        cookie_name(),
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        secure=get_settings().production,
        samesite="lax",
        path="/",
    )


def start(db: Session, response: Response, user: User) -> None:
    token = secrets.token_urlsafe(32)
    db.add(SessionRow(user_id=user.id, token_hash=_digest(token), expires_at=clock.now() + _ttl(user)))
    db.commit()
    _set_cookie(response, token, _ttl(user))


def end(db: Session, request: Request, response: Response) -> None:
    if token := request.cookies.get(cookie_name()):
        db.execute(delete(SessionRow).where(SessionRow.token_hash == _digest(token)))
        db.commit()
    response.delete_cookie(cookie_name(), path="/", secure=get_settings().production, httponly=True)


def current_user(request: Request, response: Response, db: Annotated[Session, Depends(get_db)]) -> User:
    token = request.cookies.get(cookie_name())
    row = None
    if token:
        row = db.execute(
            select(SessionRow, User)
            .join(User, User.id == SessionRow.user_id)
            .where(SessionRow.token_hash == _digest(token), SessionRow.expires_at > clock.now())
        ).first()
    if row is None:
        raise HTTPException(status_code=401, detail="Entre na sua conta para continuar.")
    session, user = row
    if token and clock.now() + _ttl(user) - session.expires_at > _extend_after(user):
        session.expires_at = clock.now() + _ttl(user)
        db.commit()
        _set_cookie(response, token, _ttl(user))  # the browser's copy lives as long as the session
    return user


CurrentUser = Annotated[User, Depends(current_user)]
