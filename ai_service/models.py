from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str


class PriceResult(BaseModel):
    symbol: str
    price: float
    currency: str = "USD"
    sources: list[str]
    timestamp: str


class ErrorResult(BaseModel):
    error: str
    symbol: Optional[str] = None


class QueryResponse(BaseModel):
    result: Union[PriceResult, ErrorResult]
    confidence: float
