from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ArticleTask(BaseModel):
    """Represents an article task from the JSON input."""

    id: str = Field(...)
    url: HttpUrl = Field(...)
    source: str = Field(...)
    category: str = Field(...)
    priority: Literal["high", "medium", "low"] = Field(...)


class ScrapedContent(BaseModel):
    """Represents the scraped content from an article."""

    title: str = Field(...)
    meta_description: str | None = Field(None)
    author: str | None = Field(None)
    published_date: str | None = Field(None)
    http_status: int = Field(...)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ArticleDocument(BaseModel):
    """Complete article document stored in MongoDB."""

    # Original task fields
    id: str = Field(..., alias="_id")
    url: str = Field(...)
    source: str = Field(...)
    category: str = Field(...)
    priority: Literal["high", "medium", "low"] = Field(...)

    # Scraped content
    title: str | None = Field(None)
    meta_description: str | None = Field(None)
    author: str | None = Field(None)
    published_date: str | None = Field(None)
    http_status: int | None = Field(None)

    # Metadata
    scraped_at: datetime | None = Field(None)
    status: Literal["pending", "success", "failed"] = Field(default="pending")
    attempts: int = Field(default=0)
    error_message: str | None = Field(None)

    class Config:
        # Allow using _id as alias
        populate_by_name = True
