import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def get_accounts() -> list[dict]:
    """Fetch all accounts from Actual Budget via bridge."""
    response = httpx.get(f"{settings.actual_bridge_url}/accounts", timeout=30.0)
    response.raise_for_status()
    accounts = response.json()
    logger.info(f"Fetched {len(accounts)} accounts from Actual Budget")
    return accounts


def get_categories() -> list[dict]:
    """Fetch all categories from Actual Budget via bridge."""
    response = httpx.get(f"{settings.actual_bridge_url}/categories", timeout=30.0)
    response.raise_for_status()
    categories = response.json()
    logger.info(f"Fetched {len(categories)} categories from Actual Budget")
    return categories


def add_transaction(account_id: str, transaction: dict) -> dict:
    """Add a transaction to Actual Budget via bridge."""
    payload = {
        "account_id": account_id,
        "transaction": transaction
    }
    response = httpx.post(
        f"{settings.actual_bridge_url}/transactions",
        json=payload,
        timeout=30.0
    )
    response.raise_for_status()
    result = response.json()
    logger.info(f"Added transaction: {result}")
    return result
