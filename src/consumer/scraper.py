from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from httpx import HTTPStatusError, RequestError

from shared.logger import get_logger
from shared.models import ScrapedContent

logger = get_logger(__name__)


class ArticleScraper:
    """Scraper for extracting article content from web pages."""

    def __init__(self, timeout: int = 30) -> None:
        """
        Initialize the article scraper.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def scrape(self, url: str, article_id: str) -> ScrapedContent:
        """
        Scrape article content from a given URL.

        Args:
            url: URL to scrape
            article_id: Article ID for logging context

        Returns:
            ScrapedContent with extracted data

        Raises:
            HTTPError: If request fails
            Exception: If parsing fails
        """
        logger.info("scraping_started", article_id=article_id, url=url)

        try:
            # Make HTTP request
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers=self.headers, follow_redirects=True)
                response.raise_for_status()

            logger.info(
                "http_request_success",
                article_id=article_id,
                status_code=response.status_code,
                content_length=len(response.content),
            )

            # Parse HTML
            soup = BeautifulSoup(response.content, "lxml")

            # Extract content
            title = self._extract_title(soup, article_id)
            meta_description = self._extract_meta_description(soup, article_id)
            author = self._extract_author(soup, article_id)
            published_date = self._extract_published_date(soup, article_id)

            scraped_content = ScrapedContent(
                title=title,
                meta_description=meta_description,
                author=author,
                published_date=published_date,
                http_status=response.status_code,
                scraped_at=datetime.utcnow(),
            )

            logger.info(
                "scraping_complete",
                article_id=article_id,
                title=title,
                has_description=meta_description is not None,
                has_author=author is not None,
            )

            return scraped_content

        except HTTPStatusError as error:
            logger.error(
                "http_status_error",
                article_id=article_id,
                status_code=error.response.status_code,
                error=str(error),
            )
            raise

        except RequestError as error:
            logger.error("http_request_error", article_id=article_id, error=str(error))
            raise

        except Exception as exception:
            logger.error(
                "scraping_error",
                article_id=article_id,
                error=str(exception),
                error_type=type(exception).__name__,
            )
            raise

    def _extract_title(self, soup: BeautifulSoup, article_id: str) -> str:
        """
        Extract article title from HTML.

        Tries multiple strategies:
        1. <meta property="og:title">
        2. <meta name="twitter:title">
        3. <h1> tag
        4. <title> tag

        Args:
            soup: BeautifulSoup parsed HTML
            article_id: Article ID for logging

        Returns:
            Extracted title or "Untitled" if not found
        """
        # Try Open Graph title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Try Twitter title
        twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
        if twitter_title and twitter_title.get("content"):
            return twitter_title["content"].strip()

        # Try h1 tag
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # Fallback to title tag
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        logger.warning("title_not_found", article_id=article_id)

        return "Untitled"

    def _extract_meta_description(self, soup: BeautifulSoup, article_id: str) -> str | None:
        """
        Extract meta description from HTML.

        Tries:
        1. <meta name="description">
        2. <meta property="og:description">

        Args:
            soup: BeautifulSoup parsed HTML
            article_id: Article ID for logging

        Returns:
            Meta description or None if not found
        """
        # Try standard meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"].strip()

        # Try Open Graph description
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            return og_desc["content"].strip()

        logger.debug("meta_description_not_found", article_id=article_id)

        return None

    def _extract_author(self, soup: BeautifulSoup, article_id: str) -> str | None:
        """
        Extract author from HTML.

        Tries:
        1. <meta name="author">
        2. <meta property="article:author">
        3. Common author class/id patterns

        Args:
            soup: BeautifulSoup parsed HTML
            article_id: Article ID for logging

        Returns:
            Author name or None if not found
        """
        # Try meta author tag
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            return meta_author["content"].strip()

        # Try article:author
        article_author = soup.find("meta", property="article:author")
        if article_author and article_author.get("content"):
            return article_author["content"].strip()

        # Try common author patterns
        author_patterns = [
            {"class_": "author"},
            {"class_": "author-name"},
            {"itemprop": "author"},
            {"rel": "author"},
        ]

        for pattern in author_patterns:
            author_tag = soup.find(attrs=pattern)
            if author_tag:
                author_text = author_tag.get_text(strip=True)
                if author_text:
                    return author_text

        logger.debug("author_not_found", article_id=article_id)

        return None

    def _extract_published_date(self, soup: BeautifulSoup, article_id: str) -> str | None:
        """
        Extract published date from HTML.

        Tries:
        1. <meta property="article:published_time">
        2. <time> tag with datetime attribute
        3. Common date class patterns

        Args:
            soup: BeautifulSoup parsed HTML
            article_id: Article ID for logging

        Returns:
            Published date string or None if not found
        """
        # Try article:published_time
        published_time = soup.find("meta", property="article:published_time")
        if published_time and published_time.get("content"):
            return published_time["content"].strip()

        # Try time tag with datetime
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            return time_tag["datetime"].strip()

        # Try common date patterns
        date_patterns = [
            {"class_": "published"},
            {"class_": "date"},
            {"class_": "post-date"},
            {"itemprop": "datePublished"},
        ]

        for pattern in date_patterns:
            date_tag = soup.find(attrs=pattern)
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                if date_text:
                    return date_text

        logger.debug("published_date_not_found", article_id=article_id)

        return None
