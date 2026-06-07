/**
 * MATE Intelligence Telegram Bot
 *
 * Connects Telegram users directly to the MATE AI intelligence layer.
 * 2 Public Models: NOVA and VANTA
 *
 * Usage:
 *   1. Create a bot via @BotFather on Telegram
 *   2. Set TELEGRAM_BOT_TOKEN in .env
 *   3. Run: npm start
 *
 * Commands:
 *   /start     — Welcome message with model selector
 *   /nova      — Switch to Mate Nova (fast response & market intelligence)
 *   /vanta     — Switch to Mate Vanta (agent execution & validation)
 *   /models    — Show available models
 *   /clear     — Clear conversation history
 *   /search    — Web search (e.g., /search gold price today)
 *   /help      — Show help message
 */

import { Telegraf, Markup } from 'telegraf';
import { getModel, getModelSummary, getModelIds } from './models.js';
import { chat, webSearch, getStatus, clearMemory } from './ai.js';

// ─── Configuration ──────────────────────────────────────────────────────────────

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;

if (!BOT_TOKEN) {
  console.error(`
╔══════════════════════════════════════════════════════════╗
║  MATE Telegram Bot — Configuration Required             ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Set your Telegram bot token:                            ║
║                                                          ║
║    export TELEGRAM_BOT_TOKEN=your_bot_token_here         ║
║                                                          ║
║  Or create a .env file:                                  ║
║    echo "TELEGRAM_BOT_TOKEN=your_token" > .env           ║
║                                                          ║
║  Get a token from @BotFather on Telegram:                ║
║    1. Message @BotFather                                 ║
║    2. Send /newbot                                       ║
║    3. Follow the instructions                            ║
║    4. Copy the token you receive                         ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
  `);
  process.exit(1);
}

// ─── Per-chat model selection state ─────────────────────────────────────────────

const chatModels = new Map(); // chatId -> modelId

function getChatModel(chatId) {
  return chatModels.get(String(chatId)) || 'nova';
}

function setChatModel(chatId, modelId) {
  chatModels.set(String(chatId), modelId);
}

// ─── Telegram markdown escaper ──────────────────────────────────────────────────

function escapeHTML(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Convert markdown-style formatting to Telegram HTML
 */
function mdToHTML(text) {
  if (!text) return '';

  // Code blocks (``` ... ```)
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre>${escapeHTML(code.trim())}</pre>`;
  });

  // Inline code (` ... `)
  text = text.replace(/`([^`]+)`/g, (_, code) => `<code>${escapeHTML(code)}</code>`);

  // Bold (** or *)
  text = text.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  text = text.replace(/\*([^*]+)\*/g, '<b>$1</b>');

  return text;
}

/**
 * Send a response, splitting into chunks if too long for Telegram (4096 char limit)
 */
async function sendMessage(ctx, text, extra = {}) {
  const MAX_LENGTH = 4000;

  if (text.length <= MAX_LENGTH) {
    return ctx.reply(text, { parse_mode: 'HTML', ...extra });
  }

  const paragraphs = text.split('\n\n');
  let chunk = '';

  for (const para of paragraphs) {
    if ((chunk + '\n\n' + para).length > MAX_LENGTH && chunk) {
      await ctx.reply(chunk.trim(), { parse_mode: 'HTML', ...extra });
      chunk = para;
    } else {
      chunk = chunk ? chunk + '\n\n' + para : para;
    }
  }

  if (chunk.trim()) {
    await ctx.reply(chunk.trim(), { parse_mode: 'HTML', ...extra });
  }
}

// ─── Model Selector Keyboard ────────────────────────────────────────────────────

function modelKeyboard(currentModel = 'nova') {
  const models = getModelSummary();
  const rows = [];

  for (let i = 0; i < models.length; i += 2) {
    const row = [];
    for (let j = 0; j < 2 && i + j < models.length; j++) {
      const m = models[i + j];
      const isActive = m.id === currentModel;
      row.push(
        Markup.button.callback(
          `${isActive ? '● ' : ''}${m.emoji} ${m.name}`,
          `model:${m.id}`
        )
      );
    }
    rows.push(row);
  }

  return Markup.inlineKeyboard(rows);
}

// ─── Bot Setup ──────────────────────────────────────────────────────────────────

const bot = new Telegraf(BOT_TOKEN);

// ─── /start ─────────────────────────────────────────────────────────────────────

bot.command('start', async (ctx) => {
  const name = ctx.from?.first_name || 'there';

  const welcome = `<b>MATE Intelligence</b>

Hey ${escapeHTML(name)} — welcome to MATE.

⚡ <b>Mate Nova</b> — Fast chat, market intelligence, deep analysis
🛡 <b>Mate Vanta</b> — Agent mode, building, coding, validation

<b>Markets are the specialty. Everything is the scope.</b>

Tap a model below to switch, or just start typing — defaults to Nova.`;

  await sendMessage(ctx, welcome, modelKeyboard('nova'));
});

// ─── /help ───────────────────────────────────────────────────────────────────────

bot.command('help', async (ctx) => {
  const help = `<b>MATE — Command Reference</b>

<b>Model Switching:</b>
/nova — Fast response & market intelligence (default)
/vanta — Agent execution & validation

<b>Other Commands:</b>
/models — Show models with selector
/clear — Clear conversation memory
/search — Web search (e.g., /search gold price)
/start — Welcome & model selector
/help — This message

<b>Tips:</b>
• Just type naturally — no commands needed
• Switch models anytime with /nova or /vanta
• Each model remembers your conversation
• Use /clear to start fresh
• Markets are the specialty, but ask about anything`;

  await sendMessage(ctx, help);
});

// ─── /models ─────────────────────────────────────────────────────────────────────

bot.command('models', async (ctx) => {
  const current = getChatModel(ctx.chat.id);
  const model = getModel(current);

  const text = `<b>MATE Intelligence</b>

Currently active: ${model.emoji} <b>Mate ${model.name}</b> — ${model.role}

Select a model below:`;

  await sendMessage(ctx, text, modelKeyboard(current));
});

// ─── /clear ──────────────────────────────────────────────────────────────────────

bot.command('clear', async (ctx) => {
  clearMemory(String(ctx.chat.id));
  await ctx.reply('Conversation memory cleared. Fresh start.');
});

// ─── /search ─────────────────────────────────────────────────────────────────────

bot.command('search', async (ctx) => {
  const query = ctx.message.text.replace(/^\/search\s*/i, '').trim();

  if (!query) {
    await ctx.reply('Usage: /search <your search query>\nExample: /search gold price today');
    return;
  }

  await ctx.replyWithChatAction('typing');

  try {
    const results = await webSearch(query);

    if (!results || results.length === 0) {
      await ctx.reply('No results found. Try a different query.');
      return;
    }

    let response = `<b>Search: ${escapeHTML(query)}</b>\n\n`;

    for (const r of results.slice(0, 5)) {
      response += `<b>${escapeHTML(r.name || r.title || 'Result')}</b>\n`;
      response += `${escapeHTML(r.snippet || r.content || '')}\n`;
      if (r.url) response += `<code>${escapeHTML(r.url)}</code>\n`;
      response += '\n';
    }

    await sendMessage(ctx, response);

  } catch (error) {
    console.error('[Search Error]', error);
    await ctx.reply('Search failed. Please try again.');
  }
});

// ─── Model Switch Commands ──────────────────────────────────────────────────────

const modelCommands = getModelIds();

for (const modelId of modelCommands) {
  bot.command(modelId, async (ctx) => {
    const model = getModel(modelId);
    setChatModel(ctx.chat.id, modelId);

    const text = `${model.emoji} <b>Switched to Mate ${model.name}</b>\n${model.role}\n\n${model.description}`;

    await sendMessage(ctx, text, modelKeyboard(modelId));
  });
}

// ─── Model Selection Callback ────────────────────────────────────────────────────

bot.action(/^model:(.+)$/, async (ctx) => {
  const modelId = ctx.match[1];
  const model = getModel(modelId);

  if (!model || !model.id) {
    await ctx.answerCbQuery('Unknown model');
    return;
  }

  setChatModel(ctx.chat.id, modelId);

  await ctx.answerCbQuery(`Switched to Mate ${model.name}`);

  const text = `${model.emoji} <b>Mate ${model.name}</b> — ${model.role}\n\n${model.description}`;

  try {
    await ctx.editMessageText(text, {
      parse_mode: 'HTML',
      ...modelKeyboard(modelId),
    });
  } catch {
    await sendMessage(ctx, text, modelKeyboard(modelId));
  }
});

// ─── Message Handler (the main chat flow) ────────────────────────────────────────

bot.on('text', async (ctx) => {
  // Skip commands (already handled)
  if (ctx.message.text.startsWith('/')) return;

  const chatId = String(ctx.chat.id);
  const userMessage = ctx.message.text;
  const currentModelId = getChatModel(chatId);
  const model = getModel(currentModelId);

  // Show typing indicator
  await ctx.replyWithChatAction('typing');

  try {
    const startTime = Date.now();
    const result = await chat(chatId, userMessage, currentModelId);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

    // Format the response with model branding
    const prefix = `${model.emoji} <b>Mate ${model.name}</b>`;
    const suffix = `\n\n<code>${elapsed}s · ${result.source === 'ai' ? 'AI' : result.source}</code>`;
    const formattedResponse = mdToHTML(result.response);

    const fullMessage = `${prefix}\n\n${formattedResponse}${suffix}`;

    await sendMessage(ctx, fullMessage);

  } catch (error) {
    console.error('[Chat Error]', error);
    await ctx.reply(`Mate ${model.name} encountered an error. Please try again.`);
  }
});

// ─── Error Handling ──────────────────────────────────────────────────────────────

bot.catch((err, ctx) => {
  console.error('[Bot Error]', `Update type: ${ctx.updateType}`, err);
});

// ─── Launch ──────────────────────────────────────────────────────────────────────

async function launch() {
  try {
    console.log('');
    console.log('╔══════════════════════════════════════════════════╗');
    console.log('║       MATE Intelligence Telegram Bot             ║');
    console.log('╠══════════════════════════════════════════════════╣');
    console.log('║                                                  ║');
    console.log('║  2 Public Models                                 ║');
    console.log('║  ⚡ NOVA  · Fast Response & Market Intelligence  ║');
    console.log('║  🛡 VANTA · Agent Execution & Validation         ║');
    console.log('║                                                  ║');
    console.log('║  Markets are the specialty.                      ║');
    console.log('║  Everything is the scope.                        ║');
    console.log('║                                                  ║');

    const botInfo = await bot.telegram.getMe();
    console.log(`║  Bot: @${botInfo.username}                       `);
    console.log('║                                                  ║');
    console.log('╚══════════════════════════════════════════════════╝');
    console.log('');

    await bot.launch();
    console.log('Bot is running. Press Ctrl+C to stop.');

    process.once('SIGINT', () => bot.stop('SIGINT'));
    process.once('SIGTERM', () => bot.stop('SIGTERM'));

  } catch (error) {
    console.error('Failed to launch bot:', error.message);

    if (error.message.includes('401') || error.message.includes('Unauthorized')) {
      console.error('');
      console.error('Your TELEGRAM_BOT_TOKEN appears to be invalid.');
      console.error('Please check your token from @BotFather.');
    }

    process.exit(1);
  }
}

launch();
