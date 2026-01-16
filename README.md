# Telegram Budget Sync

A system that allows you to log expenses via Telegram and automatically sync them to [Actual Budget](https://actualbudget.org/).

## Features

- **Natural Language Processing**: Send messages like "rm50 food and rm30 transport" and have them automatically parsed
- **Batch Processing**: Multiple messages are processed in a single Gemini API call for efficiency
- **Multi-Transaction Support**: A single message can contain multiple transactions that are split automatically
- **Telegram Notifications**: Receive a summary notification when transactions are synced
- **Auto-Restart**: Services automatically restart on system reboot

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Telegram   │────▶│   Supabase   │────▶│ Sync Service │
│    Bot      │     │ Edge Function│     │   (Python)   │
└─────────────┘     └──────────────┘     └──────────────┘
                           │                    │
                           ▼                    ▼
                    ┌──────────────┐     ┌──────────────┐
                    │  PostgreSQL  │     │ Gemini AI    │
                    │ transactions │     │   (Parse)    │
                    └──────────────┘     └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │Actual Bridge │
                                        │  (Node.js)   │
                                        └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │Actual Budget │
                                        └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │  Telegram    │
                                        │ Notification │
                                        └──────────────┘
```

## Components

### 1. Supabase Edge Function (`/supabase`)
Telegram webhook handler that receives messages and stores them in the `transactions` table.

### 2. Sync Service (`/sync-service`)
Python FastAPI service that:
- Polls Supabase for unsynced messages every 5 minutes
- Uses Gemini AI (gemini-2.5-flash-lite) to parse natural language into transaction data
- Batches multiple messages into a single API call
- Splits multi-transaction messages automatically (e.g., "rm50 food and rm30 transport" → 2 transactions)
- Sends parsed transactions to Actual Budget via the bridge
- Sends Telegram notification with sync summary

### 3. Actual Bridge (`/actual-bridge`)
Node.js Express service that wraps the Actual Budget API, providing HTTP endpoints for the Python service.

## Prerequisites

- Docker & Docker Compose
- Supabase project
- Telegram Bot (via @BotFather)
- Google Gemini API key
- Self-hosted Actual Budget instance

## Database Setup

Create the transactions table in Supabase:

```sql
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  message TEXT NOT NULL,
  synced BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Deployment

### 1. Deploy Telegram Webhook (Supabase Edge Function)

```bash
# Set the bot token secret
supabase secrets set TELEGRAM_BOT_TOKEN=your_bot_token --project-ref your-project-ref

# Deploy the function
supabase functions deploy telegram-bot --no-verify-jwt

# Set up webhook
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<PROJECT_REF>.supabase.co/functions/v1/telegram-bot"}'
```

### 2. Deploy Sync Service & Actual Bridge

```bash
cd sync-service

# Copy and configure environment
cp .env.example .env
# Edit .env with your values

# Run with Docker Compose
docker compose up --build -d
```

## Configuration

### Environment Variables (sync-service/.env)

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `SYNC_INTERVAL_MINUTES` | Polling interval (default: 5) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `ACTUAL_SERVER_URL` | Actual Budget server URL |
| `ACTUAL_PASSWORD` | Actual Budget password |
| `ACTUAL_BUDGET_ID` | Budget Sync ID (Settings → Advanced) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID for notifications |

### Getting Your Telegram Chat ID

Message `@userinfobot` or `@RawDataBot` on Telegram to get your chat ID.

## Usage

Send messages to your Telegram bot in natural language:

```
spent rm15 on lunch
coffee 8.50
rm50 food and rm30 transport
grabbed groceries for 45, rm20 on gas
```

The system will:
1. Save the message to Supabase
2. Parse it with Gemini AI to extract amount, payee, category
3. Split multi-transaction messages into separate transactions
4. Create transactions in Actual Budget
5. Send you a Telegram notification with the sync summary

### Example Notification

```
✅ Budget Sync Complete

• food: RM50.00 (Food)
• transport: RM30.00 (General)

Total: RM80.00
Transactions: 2
```

## API Endpoints

### Sync Service (port 8000)
- `GET /health` - Health check
- `POST /sync` - Manually trigger sync

### Actual Bridge (port 3002)
- `GET /health` - Health check
- `GET /accounts` - List all accounts
- `GET /categories` - List all categories
- `POST /transactions` - Add a transaction

## Development

```bash
# Run locally without Docker
cd sync-service
pip install -r requirements.txt
uvicorn app.main:app --reload

# Run actual-bridge locally
cd actual-bridge
npm install
npm start
```

## License

MIT
