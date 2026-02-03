# Publisher-Subscriber Article Scraping Pipeline

A production-grade, type-safe article scraping pipeline built with Python 3.14+ that demonstrates publisher-subscriber pattern with Redis queues, MongoDB storage, and Discord webhook notifications.

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Features](#-features)
- [Technology Stack](#-technology-stack)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
- [Running the Application](#-running-the-application)
- [Database Configuration](#-database-configuration)
- [Discord Webhook Integration](#-discord-webhook-integration)
- [Project Structure](#-project-structure)
- [Error Handling](#-error-handling)
- [Monitoring & Logs](#-monitoring--logs)
- [Development](#-development)

---

## 🏗️ Architecture

### Workflow Architecture Diagram

```text
┌─────────────────┐
│ articles.json   │
│ (10 articles)   │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ PUBLISHER                                            │
│ ┌──────────────────────────────────────────────────┐ │
│ │ 1. Load & validate JSON with Pydantic            │ │
│ │ 2. Serialize ArticleTask objects                 │ │
│ │ 3. Push tasks to Redis queue (LPUSH)             │ │
│ │ 4. Exit after completion                         │ │
│ └──────────────────────────────────────────────────┘ │
└────────┬─────────────────────────────────────────────┘
         │
         ▼
    ┌─────────┐
    │ REDIS   │ ◄─── Main Queue: article_queue
    │ QUEUE   │      DLQ: article_queue:failed
    └────┬────┘
         │
         │ BRPOP (blocking pop)
         ▼
┌──────────────────────────────────────────────────────┐
│ CONSUMER                                             │
│ ┌──────────────────────────────────────────────────┐ │
│ │ 1. Pop task from Redis (blocking)                │ │
│ │ 2. Scrape article (httpx + BeautifulSoup)        │ │
│ │ 3. Retry on failure (3 attempts, exp. backoff)   │ │
│ │ 4. Store result in MongoDB                       │ │
│ │ 5. Send Discord webhook notification             │ │
│ │ 6. Move to DLQ if all retries fail               │ │
│ └──────────────────────────────────────────────────┘ │
└─────┬──────────────────────────────┬─────────────────┘
      │                              │
      ▼                              ▼
 ┌──────────┐                   ┌─────────┐
 │ MongoDB  │                   │ Discord │
 │ Database │                   │ Webhook │
 └──────────┘                   └─────────┘
   articles                   Success/Failure
  collection                   Notifications
```

### Database ERD (Entity Relationship Diagram)

```text
┌─────────────────────────────────────────────────────────────┐
│                       MongoDB Collection                    │
│                        "articles"                           │
├─────────────────────────────────────────────────────────────┤
│ _id: String (PK)                    # Article ID            │
│ url: String (UNIQUE INDEX)          # Article URL           │
│ source: String                      # News source           │
│ category: String                    # Article category      │
│ priority: String                    # high/medium/low       │
│ ─────────────────────────────────────────────────────────── │
│ title: String?                      # Scraped title         │
│ meta_description: String?           # Meta description      │
│ author: String?                     # Article author        │
│ published_date: String?             # Publish date          │
│ http_status: Integer?               # HTTP status code      │
│ ─────────────────────────────────────────────────────────── │
│ scraped_at: DateTime?               # Scrape timestamp      │
│ status: String                      # pending/success/fail  │
│ attempts: Integer                   # Retry count           │
│ error_message: String?              # Error details         │
└─────────────────────────────────────────────────────────────┘

Indexes:
  1. _id (Primary Key, Automatic)
  2. url_unique_index (Unique) → Prevents duplicate URLs
  3. status_index → Fast filtering by status
  4. scraped_at_index → Time-based queries
  5. status_scraped_at_index (Compound) → Optimized queries
```

---

## ✨ Features

### Core Features

- ✅ **Publisher-Subscriber Pattern** - Decoupled architecture with Redis message queue
- ✅ **Type Safety** - Full type hints with Pydantic validation and Pyrefly type checking
- ✅ **Web Scraping** - Robust scraping with httpx + BeautifulSoup (lxml parser)
- ✅ **Error Handling** - Comprehensive error handling for invalid HTML, unreachable URLs, network failures
- ✅ **Retry Mechanism** - 3 retry attempts with exponential backoff (1s, 2s, 4s)
- ✅ **Dead Letter Queue** - Failed tasks moved to DLQ after max retries
- ✅ **Duplicate Prevention** - Unique indexes on both article ID and URL
- ✅ **Structured Logging** - JSON-formatted logs with structlog for observability
- ✅ **Graceful Shutdown** - SIGINT/SIGTERM handlers for clean termination
- ✅ **Docker Compose** - Fully containerized with service orchestration

### Innovative Feature: Discord Webhook Notifications

**Real-time notifications** sent to Discord for each article processed:

**Success Notifications (Green):**

- Article ID, Source, Category
- Scraped Title
- Article URL
- HTTP Status Code
- Timestamp

**Failure Notifications (Red):**

- Article ID, Source
- Number of Attempts
- Article URL
- Error Message
- Timestamp

This provides instant visibility into pipeline status, enabling quick response to issues without manual log monitoring.

---

## 🛠️ Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | ≥3.14 |
| Package Manager | uv | latest |
| Type Checker | Pyrefly | latest |
| Linter/Formatter | Ruff | latest |
| Validation | Pydantic | ≥2.12.5 |
| Configuration | pydantic-settings | ≥2.12.0 |
| Queue | Redis | alpine |
| Database | MongoDB | noble |
| HTTP Client | httpx | ≥0.28.1 |
| HTML Parser | BeautifulSoup4 + lxml | ≥4.14.3, ≥6.0.2 |
| Logging | structlog | ≥25.5.0 |
| Containerization | Docker + Docker Compose | latest |

---

## 📦 Prerequisites

### System Requirements

- Python 3.14 or higher
- Docker and Docker Compose
- uv package manager
- 2GB RAM minimum
- 1GB disk space

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Install Docker

Follow official guides:

- [Docker Desktop](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

---

## 🚀 Installation & Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd pub-sub-task
```

### 2. Install Dependencies

```bash
# Generate lockfile and install dependencies
uv lock
uv sync
```

### 3. Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Discord webhook URL
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN
```

### 4. Prepare Articles Data

Ensure `data/articles.json` exists with your article URLs:

```json
{
  "articles": [
    {
      "id": "001",
      "url": "https://example.com/article",
      "source": "Example News",
      "category": "tech",
      "priority": "high"
    }
  ]
}
```

---

## 🎮 Running the Application

### Option 1: Docker Compose (Recommended)

```bash
# Build and start all services
sudo docker compose up --build

# Or run in detached mode
sudo docker compose up --build -d

# View logs
sudo docker compose logs -f

# Stop all services
sudo docker compose down

# Clean shutdown with volume removal
sudo docker compose down -v
```

### Option 2: Local Development

**Terminal 1 - Redis:**

```bash
docker run -d -p 6379:6379 redis:alpine
```

**Terminal 2 - MongoDB:**

```bash
docker run -d -p 27017:27017 mongo:noble
```

**Terminal 3 - Publisher:**

```bash
uv run python -m src.publisher.main
```

**Terminal 4 - Consumer:**

```bash
uv run python -m src.consumer.main
```

---

## 💾 Database Configuration

### MongoDB Connection

The MongoDB connection is configured via environment variables:

```bash
# docker-compose.yaml uses internal Docker network
MONGODB_URI=mongodb://mongodb:27017/article_pipeline

# For local development
MONGODB_URI=mongodb://localhost:27017/article_pipeline
```

### Automatic Index Creation

Indexes are **automatically created** when the consumer starts via `ensure_indexes()` function:

1. **url_unique_index** (Unique) - Prevents duplicate URLs
2. **status_index** - Fast filtering by processing status
3. **scraped_at_index** - Time-based queries
4. **status_scraped_at_index** - Compound index for optimized queries

No manual database setup required!

### Manual Database Inspection

```bash
# Connect to MongoDB container
sudo docker exec -it article-pipeline-mongodb mongosh

# Switch to database
use article_pipeline

# View all articles
db.articles.find().pretty()

# Count by status
db.articles.countDocuments({status: "success"})
db.articles.countDocuments({status: "failed"})

# List indexes
db.articles.getIndexes()
```

---

## 🔔 Discord Webhook Integration

### Setup Instructions

1. **Create Discord Webhook:**
   - Open Discord server settings
   - Navigate to Integrations → Webhooks
   - Click "New Webhook"
   - Copy webhook URL

2. **Configure Environment:**

   ```bash
   # Add to .env file
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcdefghijklmnop
   ```

3. **Test Webhook:**
   Run the pipeline and check Discord for notifications

### Notification Format

**Success Message:**

```text
✅ Article Scraped Successfully
Article ID: 001
Source: Example News
Category: tech
Title: Article Title Here
URL: https://example.com/article
HTTP Status: 200
```

**Failure Message:**

```text
❌ Article Scraping Failed
Article ID: 002
Source: Example News
Attempts: 3
URL: https://example.com/bad-url
Error: HTTPStatusError: 404 Not Found
```

---

## 📁 Project Structure

```text
pub-sub-task/
├── src/
│   ├── shared/              # Shared utilities
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   ├── models.py        # Pydantic models
│   │   ├── logger.py        # Structured logging
│   │   └── database.py      # MongoDB utilities
│   │
│   ├── publisher/           # Publisher service
│   │   ├── main.py          # Entry point
│   │   └── Dockerfile       # Container config
│   │
│   └── consumer/            # Consumer service
│       ├── main.py          # Entry point
│       ├── scraper.py       # Web scraping logic
│       └── Dockerfile       # Container config
│
├── data/
│   └── articles.json        # Input articles
│
├── docker-compose.yaml      # Service orchestration
├── pyproject.toml           # Project dependencies
├── uv.lock                  # Locked dependencies
├── .env.example             # Environment template
└── README.md                # This file
```

---

## 🛡️ Error Handling

### Handled Error Types

| Error Type | Handling Strategy |
|------------|-------------------|
| Invalid HTML | BeautifulSoup parses forgivingly; missing fields return None |
| Unreachable URL | `httpx.RequestError` caught → retry with backoff |
| HTTP Errors (4xx/5xx) | `httpx.HTTPStatusError` caught → retry with backoff |
| Network Timeout | 30s timeout → retry with backoff |
| Duplicate URL | MongoDB unique index → logged and skipped |
| Duplicate ID | MongoDB primary key → logged and skipped |

### Retry Logic

1. **Attempt 1** - Immediate
2. **Attempt 2** - 1 second delay
3. **Attempt 3** - 2 seconds delay
4. **Attempt 4** - 4 seconds delay (if configured)

After max retries:

- Task moved to Dead Letter Queue (`article_queue:failed`)
- Stored in MongoDB with `status="failed"`
- Discord notification sent with error details

### Recovering Failed Tasks

```bash
# Connect to Redis
sudo docker exec -it article-pipeline-redis redis-cli

# Check DLQ
LLEN article_queue:failed

# Move back to main queue
RPOPLPUSH article_queue:failed article_queue
```

---

## 📊 Monitoring & Logs

### Viewing Logs

```bash
# All services
sudo docker compose logs -f

# Specific service
sudo docker compose logs -f publisher
sudo docker compose logs -f consumer
```

### Log Format

All logs are structured JSON:

```json
{
  "event": "task_processing_started",
  "article_id": "001",
  "url": "https://example.com/article",
  "level": "info",
  "timestamp": "2025-02-03T10:30:45.123456Z",
  "logger": "consumer.main"
}
```

### Key Events to Monitor

- `publisher_starting` - Publisher initialization
- `task_published` - Task added to queue
- `task_processing_started` - Consumer picked up task
- `scraping_complete` - Article successfully scraped
- `task_failed_all_retries` - Task moved to DLQ
- `discord_webhook_sent` - Notification delivered

---

## 🧪 Development

### Type Checking

```bash
# Run Pyrefly type checker
pyrefly check src/
```

### Linting & Formatting

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Running Tests (if implemented)

```bash
uv run pytest
```

### Adding New Articles

1. Edit `data/articles.json`
2. Add new article objects
3. Re-run publisher:

```bash
sudo docker compose up publisher
```

---

## 📝 Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_DB` | `0` | Redis database number |
| `MONGODB_URI` | `mongodb://localhost:27017/article_pipeline` | MongoDB connection string |
| `DISCORD_WEBHOOK_URL` | *required* | Discord webhook URL |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MAX_RETRIES` | `3` | Maximum retry attempts |
| `RETRY_BACKOFF_BASE` | `1` | Base backoff time in seconds |
| `QUEUE_NAME` | `article_queue` | Main queue name |
| `DLQ_NAME` | `article_queue:failed` | Dead letter queue name |

---

## 👤 Author

Jason Lloyd T. Rodriguez

---

## 🙏 Acknowledgments

- Built as a technical demonstration of publisher-subscriber architecture
- Uses modern Python 3.14+ features
- Follows best practices
- Type safety with Pydantic and Pyrefly
- Modern tooling (uv, Ruff)
- Structured logging
- Error handling and retry logic
- Docker containerization
- Comprehensive documentation
