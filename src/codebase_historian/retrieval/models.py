"""
Data models for the hybrid retrieval index.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    DOCSTRING = "docstring"


class IndexedDocument(BaseModel):
    id: str
    text: str
    doc_type: DocumentType
    subject: str  # File path or symbol qualname
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    id: str
    text: str
    doc_type: DocumentType
    subject: str
    score: float  # Hybrid ranking score (higher is more relevant)
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
