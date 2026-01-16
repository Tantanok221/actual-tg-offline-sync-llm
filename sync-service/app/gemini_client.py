import json
import logging
from datetime import date
import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel("gemini-2.5-flash-lite")


def parse_transactions_batch(messages: list[dict], accounts: list[dict], categories: list[dict]) -> list[list[dict]]:
    """
    Use Gemini to parse multiple messages into transactions in a single API call.
    Returns a list of lists - each message maps to an array of transactions (0, 1, or more).
    """
    if not messages:
        return []

    account_names = [acc["name"] for acc in accounts]
    category_names = [cat["name"] for cat in categories if cat.get("name")]

    # Build numbered message list
    messages_text = "\n".join([
        f'{i+1}. "{msg["message"]}"'
        for i, msg in enumerate(messages)
    ])

    prompt = f"""You are a budget assistant that parses natural language messages into transaction data.

Today's date is: {date.today().isoformat()}

Available accounts: {json.dumps(account_names)}
Available categories: {json.dumps(category_names)}

Parse the following {len(messages)} messages into JSON transactions. Return a JSON array with exactly {len(messages)} elements, where each element is an array of transactions for that message.

IMPORTANT: A single message may contain MULTIPLE transactions. For example:
- "rm50 on food and rm30 on transport" should produce 2 separate transactions
- "spent rm10 on coffee" should produce 1 transaction
- "/start" or greetings should produce an empty array []

For each transaction object:
- "valid": true
- "account_name": the most appropriate account from the list
- "amount": the amount as a positive number (e.g., 10.50 for RM10.50)
- "payee_name": what was purchased or who was paid
- "category_name": the most appropriate category from the list (or null if unclear)
- "notes": any additional context
- "is_expense": true if spending money, false if receiving money (income)

Messages:
{messages_text}

Example response format for 2 messages:
[
  [{{"valid": true, "amount": 50, "payee_name": "food", ...}}, {{"valid": true, "amount": 30, "payee_name": "transport", ...}}],
  []
]

Respond with only a valid JSON array of {len(messages)} arrays, no markdown or explanation."""

    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # Clean up potential markdown code blocks
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        results = json.loads(result_text)

        # Ensure we got a list
        if not isinstance(results, list):
            logger.error(f"Gemini returned non-list: {type(results)}")
            return [[]] * len(messages)

        # Ensure correct length
        if len(results) != len(messages):
            logger.warning(f"Gemini returned {len(results)} results for {len(messages)} messages")
            while len(results) < len(messages):
                results.append([])
            results = results[:len(messages)]

        # Ensure each element is a list
        for i, r in enumerate(results):
            if not isinstance(r, list):
                results[i] = [r] if r else []

        # Count total transactions
        total_tx = sum(len(r) for r in results)
        logger.info(f"Gemini parsed {len(messages)} messages -> {total_tx} transactions")
        for i, txs in enumerate(results):
            logger.info(f"  Message [{i+1}]: {len(txs)} transaction(s)")
            for tx in txs:
                logger.info(f"    - {tx}")

        return results
    except Exception as e:
        logger.error(f"Error parsing transactions batch with Gemini: {e}")
        return [[]] * len(messages)
