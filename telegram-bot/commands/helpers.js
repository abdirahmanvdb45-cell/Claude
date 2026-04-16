/**
 * helpers.js
 *
 * Shared utilities for Telegram bot command handlers.
 * Handles n8n webhook calls with timeout, retry, and auth header.
 */

const fetch = (...args) => import('node-fetch').then(({ default: f }) => f(...args));

// Webhook route map — matches n8n webhook paths
const WEBHOOK_ROUTES = {
  'pause':      '/webhook/operator/pause',
  'resume':     '/webhook/operator/resume',
  'pauseall':   '/webhook/operator/pauseall',
  'status-one': '/webhook/operator/status',
  'status-all': '/webhook/operator/status-all',
};

/**
 * Call an n8n webhook and return the parsed JSON response.
 *
 * @param {string} command   - One of the keys in WEBHOOK_ROUTES
 * @param {object} payload   - JSON body to send
 * @param {number} [retries] - Number of retry attempts (default 2)
 * @returns {Promise<object>}
 */
async function callN8nWebhook(command, payload, retries = 2) {
  const route = WEBHOOK_ROUTES[command];
  if (!route) throw new Error(`Unknown command: ${command}`);

  const url = `${process.env.N8N_WEBHOOK_BASE_URL}${route}`;
  const secret = process.env.N8N_WEBHOOK_SECRET;

  const headers = {
    'Content-Type': 'application/json',
  };
  if (secret) {
    headers['X-Webhook-Secret'] = secret;
  }

  let lastError;
  const delays = [0, 2000, 5000]; // immediate, 2s, 5s

  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) {
      await sleep(delays[attempt] || 5000);
    }

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000); // 10s timeout

      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({ command, ...payload, timestamp: new Date().toISOString() }),
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) {
        throw new Error(`n8n returned HTTP ${response.status}: ${await response.text()}`);
      }

      const json = await response.json();
      return json;
    } catch (err) {
      lastError = err;
      if (err.name === 'AbortError') {
        lastError = new Error('n8n webhook timed out after 10 seconds.');
      }
    }
  }

  throw lastError;
}

/**
 * Format a duration in milliseconds as a human-readable string.
 * e.g. 125000 → "2 minutes 5 seconds"
 */
function formatDuration(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds} seconds`;
  return `${minutes} minute${minutes !== 1 ? 's' : ''} ${seconds} seconds`;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

module.exports = { callN8nWebhook, formatDuration };
