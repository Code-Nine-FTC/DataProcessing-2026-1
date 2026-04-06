# -*- coding: utf-8 -*-
from typing import Any

class Singleton(type):
    _instances: dict["Singleton", Any] = {}

    def __call__(cls: "Singleton", *args: Any, **kwargs: Any) -> Any:  # noqa: PLW3201
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)

        return cls._instances[cls]