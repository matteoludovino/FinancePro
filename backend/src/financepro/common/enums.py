from enum import StrEnum

from sqlalchemy import Enum


def db_enum[E: StrEnum](enum: type[E], name: str) -> Enum:
    """A StrEnum stored as VARCHAR plus a CHECK constraint: adding a member later is a plain migration."""
    return Enum(
        enum,
        native_enum=False,
        create_constraint=True,
        length=20,
        name=name,
        values_callable=lambda members: [m.value for m in members],
    )
