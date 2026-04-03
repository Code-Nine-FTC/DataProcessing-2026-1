# -*- coding: utf-8 -*-
from typing import Any, Generic, Iterable, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel | None | Iterable[Any])


class BasicResponse(BaseModel, Generic[T]):
    data: T | None = None

    class Config:
        arbitrary_types_allowed = True