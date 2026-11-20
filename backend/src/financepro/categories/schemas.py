from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from financepro.categories.taxonomy import CategoryType

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class CategoryIn(BaseModel):
    name: Name
    # Required for a top-level category; a subcategory takes its parent's.
    type: CategoryType | None = None
    parent_id: int | None = None


class CategoryPatch(BaseModel):
    name: Name | None = None
    is_archived: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: CategoryType
    parent_id: int | None
    slug: str | None
    is_archived: bool
