# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DomainSpec:
    model: Any
    geom_col: str
    filtros_map: dict[str, Any] = field(default_factory=dict)
    tipo_feature: str = ""
    geom_tipo: str = "point"
