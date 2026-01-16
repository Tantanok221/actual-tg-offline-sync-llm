const express = require('express');
const api = require('@actual-app/api');

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const ACTUAL_SERVER_URL = process.env.ACTUAL_SERVER_URL || 'http://actual-budget:5006';
const ACTUAL_PASSWORD = process.env.ACTUAL_PASSWORD || 'admin';
const ACTUAL_BUDGET_ID = process.env.ACTUAL_BUDGET_ID;
const DATA_DIR = process.env.DATA_DIR || '/tmp/actual-data';

let initialized = false;

async function initActual() {
  if (initialized) return;

  console.log(`Connecting to Actual Budget at ${ACTUAL_SERVER_URL}...`);

  await api.init({
    dataDir: DATA_DIR,
    serverURL: ACTUAL_SERVER_URL,
    password: ACTUAL_PASSWORD,
  });

  console.log(`Downloading budget: ${ACTUAL_BUDGET_ID}...`);
  await api.downloadBudget(ACTUAL_BUDGET_ID);

  initialized = true;
  console.log('Actual Budget initialized successfully');
}

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', initialized });
});

// Get all accounts
app.get('/accounts', async (req, res) => {
  try {
    await initActual();
    const accounts = await api.getAccounts();
    res.json(accounts);
  } catch (error) {
    console.error('Error fetching accounts:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get all categories
app.get('/categories', async (req, res) => {
  try {
    await initActual();
    const categories = await api.getCategories();
    res.json(categories);
  } catch (error) {
    console.error('Error fetching categories:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get all payees
app.get('/payees', async (req, res) => {
  try {
    await initActual();
    const payees = await api.getPayees();
    res.json(payees);
  } catch (error) {
    console.error('Error fetching payees:', error);
    res.status(500).json({ error: error.message });
  }
});

// Add transaction
app.post('/transactions', async (req, res) => {
  try {
    await initActual();

    const { account_id, transaction } = req.body;

    if (!account_id || !transaction) {
      return res.status(400).json({ error: 'account_id and transaction are required' });
    }

    // Amount should be in cents (negative for expenses)
    const result = await api.importTransactions(account_id, [transaction]);

    res.json(result);
  } catch (error) {
    console.error('Error adding transaction:', error);
    res.status(500).json({ error: error.message });
  }
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('Shutting down...');
  if (initialized) {
    await api.shutdown();
  }
  process.exit(0);
});

app.listen(PORT, () => {
  console.log(`Actual Bridge running on port ${PORT}`);
});
