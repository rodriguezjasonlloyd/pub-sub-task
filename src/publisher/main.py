import json
from pathlib import Path

from redis import Redis, RedisError

from shared.config import get_settings
from shared.logger import configure_logging, get_logger
from shared.models import ArticleTask

logger = get_logger(__name__)


def load_articles(file_path: Path) -> list[ArticleTask]:
    """
    Load and validate articles from JSON file.

    Args:
        file_path: Path to articles.json file

    Returns:
        List of validated ArticleTask objects

    Raises:
        FileNotFoundError: If articles.json doesn't exist
        JSONDecodeError: If JSON is malformed
        ValidationError: If article data is invalid
    """
    logger.info("loading_articles", file_path=str(file_path))

    if not file_path.exists():
        logger.error("file_not_found", file_path=str(file_path))
        raise FileNotFoundError(f"Articles file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Validate each article using Pydantic
    articles = [ArticleTask(**article) for article in data["articles"]]

    logger.info("articles_loaded", count=len(articles))

    return articles


def get_redis_client() -> Redis:
    """
    Create and return Redis client connection.

    Returns:
        Connected Redis client
    """
    settings = get_settings()

    client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
    )

    client.ping()

    logger.info(
        "redis_connected",
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
    )

    return client


def publish_tasks(client: Redis, articles: list[ArticleTask]) -> int:
    """
    Push article tasks to Redis queue.

    Args:
        client: Redis client connection
        articles: List of article tasks to publish

    Returns:
        Number of tasks published
    """
    settings = get_settings()
    published_count = 0

    for article in articles:
        task_data = article.model_dump_json()

        # Push to queue (LPUSH adds to left/head of list)
        client.lpush(settings.queue_name, task_data)

        logger.info(
            "task_published",
            article_id=article.id,
            url=str(article.url),
            priority=article.priority,
            queue=settings.queue_name,
        )

        published_count += 1

    logger.info("publishing_complete", total_published=published_count)

    return published_count


def main() -> None:
    """Main entry point for publisher service."""
    configure_logging()
    logger.info("publisher_starting")

    try:
        # Load articles from JSON
        articles_file = Path("data/articles.json")
        articles = load_articles(articles_file)

        # Connect to Redis
        redis_client = get_redis_client()

        # Publish tasks to queue
        published_count = publish_tasks(redis_client, articles)

        logger.info(
            "publisher_complete",
            total_articles=len(articles),
            published=published_count,
        )

    except FileNotFoundError as error:
        logger.error("file_error", error=str(error))
        raise

    except RedisError as error:
        logger.error("redis_error", error=str(error))
        raise

    except Exception as exception:
        logger.error("unexpected_error", error=str(exception), error_type=type(exception).__name__)
        raise


if __name__ == "__main__":
    main()
