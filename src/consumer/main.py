import json
import signal
import sys
import time
from datetime import datetime

import httpx
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from redis import Redis

from consumer.scraper import ArticleScraper
from shared.config import get_settings
from shared.database import ensure_indexes
from shared.logger import configure_logging, get_logger
from shared.models import ArticleDocument, ArticleTask, ScrapedContent

logger = get_logger(__name__)

# Global flag for graceful shutdown
shutdown_flag: bool = False


def signal_handler(signum: int, _frame: object) -> None:
    """Handle shutdown signals for graceful termination."""
    global shutdown_flag
    shutdown_flag = True
    logger.info("shutdown_signal_received", signal=signum, shutdown_flag=shutdown_flag)


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
    )

    return client


def get_mongo_client() -> MongoClient:
    """
    Create and return MongoDB client connection.

    Returns:
        Connected MongoDB client
    """
    settings = get_settings()

    client = MongoClient(settings.mongodb_uri)

    # Test connection
    client.admin.command("ping")

    # Extract database name from URI
    db_name = settings.mongodb_uri.split("/")[-1].split("?")[0]
    logger.info("mongodb_connected", database=db_name)

    return client


def send_discord_webhook(
    webhook_url: str,
    article_task: ArticleTask,
    success: bool,
    scraped_content: ScrapedContent | None = None,
    error_message: str | None = None,
    attempts: int = 1,
) -> None:
    """
    Send notification to Discord webhook.

    Args:
        webhook_url: Discord webhook URL
        article_task: Original article task
        success: Whether scraping succeeded
        scraped_content: Scraped content if successful
        error_message: Error message if failed
        attempts: Number of attempts made
    """
    try:
        if success and scraped_content:
            embed = {
                "title": "✅ Article Scraped Successfully",
                "color": 0x00FF00,
                "fields": [
                    {"name": "Article ID", "value": article_task.id, "inline": True},
                    {"name": "Source", "value": article_task.source, "inline": True},
                    {"name": "Category", "value": article_task.category, "inline": True},
                    {"name": "Title", "value": scraped_content.title, "inline": False},
                    {"name": "URL", "value": str(article_task.url), "inline": False},
                    {
                        "name": "HTTP Status",
                        "value": str(scraped_content.http_status),
                        "inline": True,
                    },
                ],
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            embed = {
                "title": "❌ Article Scraping Failed",
                "color": 0xFF0000,
                "fields": [
                    {"name": "Article ID", "value": article_task.id, "inline": True},
                    {"name": "Source", "value": article_task.source, "inline": True},
                    {"name": "Attempts", "value": str(attempts), "inline": True},
                    {"name": "URL", "value": str(article_task.url), "inline": False},
                    {
                        "name": "Error",
                        "value": error_message or "Unknown error",
                        "inline": False,
                    },
                ],
                "timestamp": datetime.utcnow().isoformat(),
            }

        payload = {"embeds": [embed]}

        with httpx.Client(timeout=10) as client:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()

        logger.info(
            "discord_webhook_sent",
            article_id=article_task.id,
            success=success,
        )

    except Exception as exception:
        logger.error(
            "discord_webhook_failed",
            article_id=article_task.id,
            error=str(exception),
        )


def store_article(
    mongo_client: MongoClient,
    article_task: ArticleTask,
    scraped_content: ScrapedContent | None = None,
    status: str = "success",
    attempts: int = 1,
    error_message: str | None = None,
) -> None:
    """
    Store article data in MongoDB.

    Args:
        mongo_client: MongoDB client
        article_task: Original article task
        scraped_content: Scraped content if available
        status: Processing status
        attempts: Number of attempts made
        error_message: Error message if failed
    """
    settings = get_settings()
    db_name = settings.mongodb_uri.split("/")[-1].split("?")[0]
    db = mongo_client[db_name]
    collection = db["articles"]

    # Build document
    document_data = {
        "_id": article_task.id,
        "url": str(article_task.url),
        "source": article_task.source,
        "category": article_task.category,
        "priority": article_task.priority,
        "status": status,
        "attempts": attempts,
        "error_message": error_message,
    }

    # Add scraped content if available
    if scraped_content:
        document_data.update(
            {
                "title": scraped_content.title,
                "meta_description": scraped_content.meta_description,
                "author": scraped_content.author,
                "published_date": scraped_content.published_date,
                "http_status": scraped_content.http_status,
                "scraped_at": scraped_content.scraped_at,
            }
        )

    # Validate with Pydantic
    article_doc = ArticleDocument(**document_data)

    try:
        # Insert or update
        collection.replace_one(
            {"_id": article_task.id},
            article_doc.model_dump(by_alias=True, exclude_none=True),
            upsert=True,
        )

        logger.info(
            "article_stored",
            article_id=article_task.id,
            status=status,
            attempts=attempts,
        )

    except DuplicateKeyError:
        logger.warning("duplicate_article", article_id=article_task.id)

    except Exception as exception:
        logger.error(
            "mongodb_store_error",
            article_id=article_task.id,
            error=str(exception),
        )
        raise


def process_task(
    redis_client: Redis,
    mongo_client: MongoClient,
    scraper: ArticleScraper,
    task_data: str,
    webhook_url: str,
) -> None:
    """
    Process a single article task with retry logic.

    Args:
        redis_client: Redis client
        mongo_client: MongoDB client
        scraper: Article scraper instance
        task_data: JSON string of article task
        webhook_url: Discord webhook URL
    """
    settings = get_settings()

    # Parse task
    task_dict = json.loads(task_data)
    article_task = ArticleTask(**task_dict)

    logger.info(
        "task_processing_started",
        article_id=article_task.id,
        url=str(article_task.url),
    )

    attempt = 1
    last_error = None

    while attempt <= settings.max_retries:
        try:
            # Scrape article
            scraped_content = scraper.scrape(
                url=str(article_task.url),
                article_id=article_task.id,
            )

            # Store in MongoDB
            store_article(
                mongo_client=mongo_client,
                article_task=article_task,
                scraped_content=scraped_content,
                status="success",
                attempts=attempt,
            )

            # Send success webhook
            send_discord_webhook(
                webhook_url=webhook_url,
                article_task=article_task,
                success=True,
                scraped_content=scraped_content,
                attempts=attempt,
            )

            logger.info(
                "task_processing_complete",
                article_id=article_task.id,
                attempts=attempt,
            )

            return

        except Exception as exception:
            last_error = str(exception)

            logger.warning(
                "task_processing_failed",
                article_id=article_task.id,
                attempt=attempt,
                max_retries=settings.max_retries,
                error=last_error,
            )

            if attempt < settings.max_retries:
                # Calculate exponential backoff
                backoff_time = settings.retry_backoff_base * (2 ** (attempt - 1))
                logger.info(
                    "retry_scheduled",
                    article_id=article_task.id,
                    next_attempt=attempt + 1,
                    backoff_seconds=backoff_time,
                )
                time.sleep(backoff_time)

            attempt += 1

    # All retries exhausted - move to DLQ and store failure
    logger.error(
        "task_failed_all_retries",
        article_id=article_task.id,
        attempts=attempt - 1,
        error=last_error,
    )

    # Store failed status in MongoDB
    store_article(
        mongo_client=mongo_client,
        article_task=article_task,
        scraped_content=None,
        status="failed",
        attempts=attempt - 1,
        error_message=last_error,
    )

    # Send failure webhook
    send_discord_webhook(
        webhook_url=webhook_url,
        article_task=article_task,
        success=False,
        error_message=last_error,
        attempts=attempt - 1,
    )

    # Move to dead letter queue
    redis_client.lpush(settings.dlq_name, task_data)
    logger.info("task_moved_to_dlq", article_id=article_task.id, dlq=settings.dlq_name)


def consume_tasks() -> None:
    """Main consumer loop - continuously processes tasks from Redis queue."""
    global shutdown_flag

    settings = get_settings()

    # Initialize connections
    redis_client = get_redis_client()
    mongo_client = get_mongo_client()
    scraper = ArticleScraper()

    # Ensure MongoDB indexes exist
    ensure_indexes(mongo_client)

    logger.info(
        "consumer_started",
        queue=settings.queue_name,
        max_retries=settings.max_retries,
    )

    while not shutdown_flag:
        try:
            # Block and wait for task (timeout 1 second for responsiveness)
            result = redis_client.brpop(settings.queue_name, timeout=1)

            if result is None:
                continue

            # Extract task data
            _, task_data = result

            # Process the task
            process_task(
                redis_client=redis_client,
                mongo_client=mongo_client,
                scraper=scraper,
                task_data=task_data,
                webhook_url=str(settings.discord_webhook_url),
            )

        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")
            break

        except Exception as exception:
            logger.error(
                "consumer_loop_error",
                error=str(exception),
                error_type=type(exception).__name__,
            )

            time.sleep(1)

    logger.info("consumer_shutting_down")
    mongo_client.close()
    redis_client.close()


def main() -> None:
    """Main entry point for consumer service."""
    configure_logging()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        consume_tasks()
    except Exception as exception:
        logger.error("consumer_fatal_error", error=str(exception))
        sys.exit(1)


if __name__ == "__main__":
    main()
