from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated envelope returned by all listing endpoints.
    All fields required by the spec: items, total, page, size, total_pages.
    """
    items: List[T]
    total: int
    page: int
    size: int
    total_pages: int

    @classmethod
    def build(cls, items: List[T], total: int, page: int, size: int) -> "PaginatedResponse[T]":
        total_pages = max(1, (total + size - 1) // size)
        return cls(items=items, total=total, page=page, size=size, total_pages=total_pages)
