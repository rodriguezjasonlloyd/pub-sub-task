from pymongo import ASCENDING, MongoClient
from pymongo.errors import OperationFailure

from shared.config import get_settings
from shared.logger import get_logger

logger = get_logger(__name__)


def get_database_name() -> str:
    """
    Extract database name from MongoDB URI.

    Returns:
        Database name
    """
    settings = get_settings()
    db_name = settings.mongodb_uri.split("/")[-1].split("?")[0]
    return db_name


def ensure_indexes(client: MongoClient) -> None:
    """
    Ensure required indexes exist on the articles collection.

    This should be called once on consumer startup to guarantee
    proper duplicate handling and query performance.

    Args:
        client: MongoDB client instance

    Raises:
        OperationFailure: If index creation fails
    """
    db_name = get_database_name()
    db = client[db_name]
    collection = db["articles"]

    logger.info("ensuring_mongodb_indexes", database=db_name)

    try:
        # Create unique index on URL to prevent duplicate URLs
        collection.create_index(
            [("url", ASCENDING)],
            unique=True,
            name="url_unique_index",
        )
        logger.info("index_ensured", index="url_unique_index", unique=True)

        # Create index on status for efficient filtering
        collection.create_index(
            [("status", ASCENDING)],
            name="status_index",
        )
        logger.info("index_ensured", index="status_index")

        # Create index on scraped_at for time-based queries
        collection.create_index(
            [("scraped_at", ASCENDING)],
            name="scraped_at_index",
        )
        logger.info("index_ensured", index="scraped_at_index")

        # Create compound index for common queries (status + scraped_at)
        collection.create_index(
            [("status", ASCENDING), ("scraped_at", ASCENDING)],
            name="status_scraped_at_index",
        )
        logger.info("index_ensured", index="status_scraped_at_index")

        logger.info("mongodb_indexes_ready", collection="articles")

    except OperationFailure as error:
        logger.error("mongodb_index_creation_failed", error=str(error))
        raise
