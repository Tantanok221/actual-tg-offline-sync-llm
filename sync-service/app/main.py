import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.supabase_client import fetch_unsynced_messages, mark_as_synced
from app.actual_client import get_accounts, get_categories, add_transaction
from app.gemini_client import parse_transactions_batch
from app.telegram_client import send_sync_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def add_single_transaction(msg_id: str, parsed: dict, accounts: list[dict], categories: list[dict], tx_index: int = 0) -> dict | None:
    """Add a single parsed transaction to Actual Budget. Returns transaction info for summary or None on failure."""
    if not parsed or not parsed.get("valid"):
        return None

    # Find account ID by name
    account_name = parsed.get("account_name")
    account_id = None
    for acc in accounts:
        if acc["name"].lower() == account_name.lower():
            account_id = acc["id"]
            break

    if not account_id:
        logger.warning(f"Account not found: {account_name}")
        return None

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

    # Build transaction with unique imported_id for multiple transactions from same message
    imported_id = f"{msg_id}-{tx_index}" if tx_index > 0 else msg_id
    transaction = {
        "date": date.today().isoformat(),
        "amount": amount,
        "payee_name": parsed.get("payee_name", "Unknown"),
        "notes": parsed.get("notes") or "",
        "imported_id": imported_id,
    }

    if category_id:
        transaction["category"] = category_id

    # Add to Actual Budget
    add_transaction(account_id, transaction)
    logger.info(f"Added transaction: {parsed['payee_name']} - {parsed['amount']}")

    # Return transaction info for summary
    return {
        "amount": parsed["amount"],
        "payee_name": parsed.get("payee_name", "Unknown"),
        "category_name": category_name or "Uncategorized",
    }


def process_message_transactions(msg: dict, transactions: list[dict], accounts: list[dict], categories: list[dict]) -> tuple[bool, list[dict]]:
    """Process all transactions for a single message. Returns (success, list of added transactions)."""
    if not transactions:
        logger.info(f"No transactions in message: {msg['message'][:50]}...")
        return False, []

    added_transactions = []
    for i, tx in enumerate(transactions):
        result = add_single_transaction(msg["id"], tx, accounts, categories, i)
        if result:
            added_transactions.append(result)

    success = len(added_transactions) == len(transactions)
    logger.info(f"Message {msg['id']}: {len(added_transactions)}/{len(transactions)} transactions added")
    return success, added_transactions


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

        # Parse all messages in a single Gemini call
        logger.info(f"Parsing {len(messages)} messages with Gemini (batch)")
        parsed_results = parse_transactions_batch(messages, accounts, categories)

        # Process each message's transactions
        processed_ids = []
        all_added_transactions = []
        for msg, transactions in zip(messages, parsed_results):
            logger.info(f"Processing message: {msg['id']} - {msg['message'][:50]}...")
            success, added = process_message_transactions(msg, transactions, accounts, categories)
            if success:
                processed_ids.append(msg["id"])
                all_added_transactions.extend(added)

        # Mark processed messages as synced
        if processed_ids:
            mark_as_synced(processed_ids)

        # Send Telegram summary
        if all_added_transactions:
            send_sync_summary(len(processed_ids), all_added_transactions)

        logger.info(f"Sync job completed - {len(processed_ids)} messages, {len(all_added_transactions)} transactions")
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
