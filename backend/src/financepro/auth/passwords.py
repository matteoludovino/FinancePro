"""Argon2id with OWASP's minimum profile (19 MiB, 2 passes).

Each hash holds 19 MiB while it runs, and FastAPI runs synchronous endpoints on a pool of up to 40
threads: 40 sign-ins at once would need ~760 MB on a 512 MB instance. A semaphore caps concurrent hashes.
"""

import threading

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
_slots = threading.BoundedSemaphore(2)

# Verified when the e-mail doesn't exist, so a sign-in takes as long whether or not the account exists.
_DUMMY_HASH = _hasher.hash("an unused password, only here to spend the same time")


def hash_password(password: str) -> str:
    with _slots:
        return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    with _slots:
        try:
            return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
        except VerificationError, InvalidHashError:
            return False
