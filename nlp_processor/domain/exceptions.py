# -*- coding: utf-8 -*-
from __future__ import annotations


class NLPError(Exception):
    pass


class OutOfScopeError(NLPError):
    pass


class LowConfidenceError(NLPError):
    pass
