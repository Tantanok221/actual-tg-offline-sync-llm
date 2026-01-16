import json
import logging
from datetime import date
import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel("gemini-1.5-flash")


def parse_transaction(message: str, accounts: list[dict], categories: list[dict]) -> dict | None:
    """
    Use Gemini to parse a natural language message into a transaction.
    Returns None if the message is not a valid transaction.
    """
    account_names = [acc["name"] for acc in accounts]
    category_names = [cat["name"] for cat in categories if cat.get("name")]

    prompt = f"""You are a budget assistant that parses natural language messages into transaction data.

Today's date is: {date.today().isoformat()}

Available accounts: {json.dumps(account_names)}
Available categories: {json.dumps(category_names)}

Parse the following message into a JSON transaction. If the message is not about a financial transaction (like /start or greetings), return {{"valid": false}}.

For valid transactions, return JSON with:
- "valid": true
- "account_name": the most appropriate account from the list (use your best judgment)
- "amount": the amount as a positive number (e.g., 10.50 for RM10.50)
- "payee_name": what was purchased or who was paid
- "category_name": the most appropriate category from the list (or null if unclear)
- "notes": any additional context from the message
- "is_expense": true if spending money, false if receiving money (income)

Message: "{message}"

Respond with only valid JSON, no markdown or explanation."""

    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # Clean up potential markdown code blocks
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        result = json.loads(result_text)
        logger.info(f"Gemini parsed transaction: {result}")
        return result
    except Exception as e:
        logger.error(f"Error parsing transaction with Gemini: {e}")
        return None
