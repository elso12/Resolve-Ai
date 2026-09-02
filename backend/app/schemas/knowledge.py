"""
ResolveAI — Knowledge Base & RAG Schemas
"""

import datetime
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeArticleBase(BaseModel):
    title: str = Field(..., max_length=255, description="Article title")
    content: str = Field(..., description="Markdown content of the article")
    category: str = Field(default="General", max_length=100, description="Article category")
    is_published: bool = Field(default=True, description="Whether the article is publicly visible")


class KnowledgeArticleCreate(KnowledgeArticleBase):
    pass


class KnowledgeArticleUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    content: str | None = None
    category: str | None = Field(None, max_length=100)
    is_published: bool | None = None


class KnowledgeArticleOut(KnowledgeArticleBase):
    id: int
    slug: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleRef(BaseModel):
    id: int
    title: str
    slug: str
    category: str
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 - 1.0)")
    snippet: str = Field(default="", description="Relevant context snippet from the article")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000, description="Customer question for RAG")


class AskResponse(BaseModel):
    answer: str = Field(..., description="Grounded answer generated from knowledge base")
    sources: list[ArticleRef] = Field(default_factory=list, description="Referenced source articles")
