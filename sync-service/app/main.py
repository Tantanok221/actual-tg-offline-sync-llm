import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.supabase_client import fetch_unsynced_messages, mark_as_synced
from app.actual_client import get_accounts, get_categories, add_transaction
from app.gemini_client import parse_transaction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def process_message(msg: dict, accounts: list[dict], categories: list[dict]) -> bool:
    """Process a single message and add to Actual Budget if valid."""
    message_text = msg["message"]

    # Parse with Gemini
    parsed = parse_transaction(message_text, accounts, categories)

    if not parsed or not parsed.get("valid"):
        logger.info(f"Message not a valid transaction: {message_text[:50]}...")
        return True  # Still mark as processed

    # Find account ID by name
    account_name = parsed.get("account_name")
    account_id = None
    for acc in accounts:
        if acc["name"].lower() == account_name.lower():
            account_id = acc["id"]
            break

    if not account_id:
        logger.warning(f"Account not found: {account_name}")
        return False

    # Find category ID by name
    category_id = None
    category_name = parsed.get("category_name")
    if category_name:
        for cat in categories:
            if cat.get("name", "").lower() == category_name.lower():
                category_id = cat["id"]
                break

    # Convert amount to cents (Actual Budget uses cents)
    amount = int(float(parsed["amount"]) * 100)
    if parsed.get("is_expense", True):
        amount = -amount  # Expenses are negative

    # Build transaction
    transaction = {
        "date": date.today().isoformat(),
        "amount": amount,
        "payee_name": parsed.get("payee_name", "Unknown"),
        "notes": parsed.get("notes", ""),
        "imported_id": msg["id"],  # Use Supabase ID to prevent duplicates
    }

    if category_id:
        transaction["category"] = category_id

    # Add to Actual Budget
    add_transaction(account_id, transaction)
    logger.info(f"Added transaction: {parsed['payee_name']} - {parsed['amount']}")
    return True


async def sync_job():
    """Background job to fetch and process unsynced messages."""
    logger.info("Sync job started")
    try:
        messages = fetch_unsynced_messages()

        if not messages:
            logger.info("No unsynced messages found")
            return

        # Fetch accounts and categories once
        accounts = get_accounts()
        categories = get_categories()

        processed_ids = []
        for msg in messages:
            logger.info(f"Processing message: {msg['id']} - {msg['message'][:50]}...")
            if process_message(msg, accounts, categories):
                processed_ids.append(msg["id"])

        # Mark processed messages as synced
        if processed_ids:
            mark_as_synced(processed_ids)

        logger.info(f"Sync job completed - processed {len(processed_ids)} messages")
    except Exception as e:
        logger.error(f"Sync job failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting scheduler with {settings.sync_interval_minutes} minute interval")
    scheduler.add_job(
        sync_job,
        "interval",
        minutes=settings.sync_interval_minutes,
        id="sync_job",
        replace_existing=True
    )
    scheduler.start()
    # Run once on startup
    await sync_job()
    yield
    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler shut down")


app = FastAPI(title="Budget Sync Service", lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/sync")
async def trigger_sync():
    """Manually trigger a sync job."""
    await sync_job()
    return {"status": "sync triggered"}
