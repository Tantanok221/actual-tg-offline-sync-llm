import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def send_message(text: str, chat_id: str = None) -> bool:
    """Send a message to Telegram chat."""
    chat_id = chat_id or settings.telegram_chat_id

    try:
        response = httpx.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Sent Telegram message to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def send_sync_summary(messages_count: int, transactions: list[dict]) -> bool:
    """Send a summary of synced transactions to Telegram."""
    if not transactions:
        return True

    # Build summary message
    total_amount = sum(tx.get("amount", 0) for tx in transactions)

    lines = ["✅ <b>Budget Sync Complete</b>", ""]

    for tx in transactions:
        amount = tx.get("amount", 0)
        payee = tx.get("payee_name", "Unknown")
        category = tx.get("category_name", "Uncategorized")
        lines.append(f"• <b>{payee}</b>: RM{amount:.2f} ({category})")

    lines.append("")
    lines.append(f"<b>Total:</b> RM{total_amount:.2f}")
    lines.append(f"<b>Transactions:</b> {len(transactions)}")

    message = "\n".join(lines)
    return send_message(message)
