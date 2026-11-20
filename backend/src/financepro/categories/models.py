from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from financepro.categories.taxonomy import CategoryType
from financepro.db import Base


class Category(Base):
    """Two levels at most (Alimentação → Restaurantes), each owned by one person."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(60))
    type: Mapped[CategoryType] = mapped_column(
        Enum(
            CategoryType,
            native_enum=False,
            create_constraint=True,
            length=10,
            name="category_type",
            values_callable=lambda kinds: [k.value for k in kinds],
        )
    )
    # Ties the category to the built-in taxonomy (see taxonomy.py); NULL for categories people create.
    slug: Mapped[str | None] = mapped_column(String(40))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # COALESCE: two top-level categories can't share a name either (NULLs are distinct in UNIQUE).
        Index(
            "uq_categories_owner_parent_name",
            owner_id,
            func.coalesce(parent_id, 0),
            func.lower(name),
            unique=True,
        ),
        Index(
            "uq_categories_owner_slug", owner_id, slug, unique=True, postgresql_where=text("slug IS NOT NULL")
        ),
    )
