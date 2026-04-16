/**
 * index.js — LinkedIn Agent Telegram Bot
 *
 * Operator control panel for the LinkedIn content automation system.
 * Accepts commands from a whitelisted operator chat ID only.
 *
 * Commands:
 *   /pause {client_id}     — Emergency pause a single client's queue
 *   /resume {client_id}    — Resume a paused client
 *   /pauseall              — Pause all active clients (system-wide emergency)
 *   /status {client_id}    — Get current status for one client
 *   /status all            — Get status summary across all clients
 *
 * Each command calls an n8n webhook, which handles the actual Airtable +
 * Taplio operations atomically.
 *
 * Environment variables required (see .env.example):
 *   TELEGRAM_BOT_TOKEN
 *   TELEGRAM_OPERATOR_CHAT_ID
 *   N8N_WEBHOOK_BASE_URL
 *   N8N_WEBHOOK_SECRET
 */

require('dotenv').config();
const { Telegraf } = require('telegraf');
const { callN8nWebhook, formatDuration } = require('./commands/helpers');

// ─── Validation ───────────────────────────────────────────────────────────────

const required = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_OPERATOR_CHAT_ID', 'N8N_WEBHOOK_BASE_URL'];
required.forEach((key) => {
  if (!process.env[key]) throw new Error(`Missing required env var: ${key}`);
});

const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);
const OPERATOR_CHAT_ID = Number(process.env.TELEGRAM_OPERATOR_CHAT_ID);

// ─── Middleware: Restrict to operator only ────────────────────────────────────

bot.use(async (ctx, next) => {
  const chatId = ctx.chat?.id;
  if (chatId !== OPERATOR_CHAT_ID) {
    await ctx.reply('Unauthorised. This bot is private.');
    return;
  }
  await next();
});

// ─── /pause {client_id} ───────────────────────────────────────────────────────

bot.command('pause', async (ctx) => {
  const args = ctx.message.text.split(' ').slice(1);
  const clientId = args[0]?.trim();

  if (!clientId) {
    return ctx.reply('Usage: /pause {client_id}\nExample: /pause cus_ABC123');
  }

  await ctx.reply(`⏸ Pausing client ${clientId}...`);

  try {
    const result = await callN8nWebhook('pause', { client_id: clientId });
    await ctx.reply(
      `✅ Client paused successfully.\n\n` +
      `Client ID: ${clientId}\n` +
      `Airtable status: paused_emergency\n` +
      `Taplio queue: cleared\n` +
      `Client notified: yes\n\n` +
      `To resume: /resume ${clientId}`
    );
  } catch (err) {
    await ctx.reply(
      `❌ Pause failed: ${err.message}\n\n` +
      `Manual steps required:\n` +
      `1. Set Airtable status to paused_emergency for ${clientId}\n` +
      `2. Clear Taplio queue manually\n` +
      `3. Email client about temporary pause`
    );
  }
});

// ─── /resume {client_id} ─────────────────────────────────────────────────────

bot.command('resume', async (ctx) => {
  const args = ctx.message.text.split(' ').slice(1);
  const clientId = args[0]?.trim();

  if (!clientId) {
    return ctx.reply('Usage: /resume {client_id}\nExample: /resume cus_ABC123');
  }

  await ctx.reply(`▶️ Resuming client ${clientId}...`);

  try {
    const result = await callN8nWebhook('resume', { client_id: clientId });
    await ctx.reply(
      `✅ Client ${clientId} resumed.\n\n` +
      `Airtable status: active\n` +
      `Monitor Taplio to confirm next post publishes at its scheduled time.`
    );
  } catch (err) {
    await ctx.reply(
      `❌ Resume failed: ${err.message}\n\n` +
      `Manual step: Update Airtable status to "active" for ${clientId}`
    );
  }
});

// ─── /pauseall ────────────────────────────────────────────────────────────────

bot.command('pauseall', async (ctx) => {
  await ctx.reply(
    '⚠️ This will pause ALL active clients and clear ALL Taplio queues.\n\n' +
    'Send /pauseall confirm to proceed.'
  );
});

bot.hears('/pauseall confirm', async (ctx) => {
  await ctx.reply('🚨 Pausing all clients...');

  try {
    const result = await callN8nWebhook('pauseall', {});
    const count = result?.clientsPaused ?? 'unknown';
    await ctx.reply(
      `✅ System-wide pause complete.\n\n` +
      `Clients paused: ${count}\n` +
      `All Taplio queues cleared.\n\n` +
      `To resume individual clients: /resume {client_id}`
    );
  } catch (err) {
    await ctx.reply(
      `❌ Pauseall failed: ${err.message}\n\n` +
      `You must manually pause each client. Run /status all to get a list.`
    );
  }
});

// ─── /status {client_id | all} ────────────────────────────────────────────────

bot.command('status', async (ctx) => {
  const args = ctx.message.text.split(' ').slice(1);
  const target = args[0]?.trim().toLowerCase();

  if (!target) {
    return ctx.reply('Usage:\n/status {client_id}\n/status all');
  }

  await ctx.reply(`🔍 Fetching status for: ${target}...`);

  try {
    if (target === 'all') {
      const result = await callN8nWebhook('status-all', {});
      const { summary } = result;
      await ctx.reply(formatStatusAll(summary));
    } else {
      const result = await callN8nWebhook('status-one', { client_id: target });
      await ctx.reply(formatStatusOne(result));
    }
  } catch (err) {
    await ctx.reply(`❌ Status fetch failed: ${err.message}`);
  }
});

// ─── /help ────────────────────────────────────────────────────────────────────

bot.command('help', async (ctx) => {
  await ctx.reply(
    `LinkedIn Agent — Operator Commands\n\n` +
    `/pause {client_id}     Emergency stop a single client\n` +
    `/resume {client_id}    Resume a paused client\n` +
    `/pauseall              Stop ALL clients (confirm required)\n` +
    `/status {client_id}    Status for one client\n` +
    `/status all            Status summary for all clients\n\n` +
    `Alerts are sent automatically for:\n` +
    `• Claude generation failures\n` +
    `• Taplio scheduling failures\n` +
    `• Revision completions\n` +
    `• Fallback content generation\n` +
    `• Email bounces\n` +
    `• Named entity flags in posts`
  );
});

// ─── Formatters ───────────────────────────────────────────────────────────────

function formatStatusOne(data) {
  if (!data || !data.client) return 'Client not found.';
  const c = data.client;
  return (
    `📋 ${c.name} (${c.client_id})\n\n` +
    `Status:          ${c.status}\n` +
    `Plan:            ${c.plan_tier}\n` +
    `Last generated:  ${c.last_content_generated || 'never'}\n` +
    `Posts scheduled: ${c.posts_scheduled ?? '—'}\n` +
    `Last doc:        ${c.last_doc_id ? 'exists' : 'none'}\n` +
    `Email:           ${c.email_status || 'ok'}`
  );
}

function formatStatusAll(summary) {
  if (!summary) return 'No data returned.';
  return (
    `📊 System Status — All Clients\n\n` +
    `Total clients:       ${summary.total}\n` +
    `Active:              ${summary.active}\n` +
    `Doc delivered:       ${summary.doc_delivered}\n` +
    `Scheduled confirmed: ${summary.scheduled_confirmed}\n` +
    `Paused (emergency):  ${summary.paused_emergency}\n` +
    `Generation failed:   ${summary.generation_failed}\n` +
    `Scheduling partial:  ${summary.scheduling_partial}\n` +
    `Cancelled:           ${summary.cancelled}\n\n` +
    `Action needed: ${summary.action_needed > 0 ? `⚠️ ${summary.action_needed} clients require attention` : '✅ None'}`
  );
}

// ─── Start ────────────────────────────────────────────────────────────────────

bot.launch(() => {
  console.log(`[${new Date().toISOString()}] Telegram bot started. Listening for commands from chat ID: ${OPERATOR_CHAT_ID}`);
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
