import logging
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )
    return _client


def fetch_unsynced_messages() -> list[dict]:
    """Fetch all transactions where synced = false."""
    client = get_client()
    response = client.table("transactions").select("*").eq("synced", False).execute()
    logger.info(f"Fetched {len(response.data)} unsynced messages")
    return response.data


def mark_as_synced(ids: list[str]) -> None:
    """Mark transactions as synced by their IDs."""
    if not ids:
        return
    client = get_client()
    client.table("transactions").update({"synced": True}).in_("id", ids).execute()
    logger.info(f"Marked {len(ids)} messages as synced")
