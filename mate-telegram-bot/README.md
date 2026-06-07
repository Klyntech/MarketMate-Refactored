# MATE Intelligence Telegram Bot

Chat with MarketMate's 6-layer AI intelligence stack directly from Telegram.

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Set your bot token
export TELEGRAM_BOT_TOKEN=your_token_from_botfather

# 3. Run
npm start
```

## Get a Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "MATE Intelligence")
4. Choose a username (e.g., "mate_intel_bot")
5. Copy the token you receive
6. Set it as `TELEGRAM_BOT_TOKEN`

## Available Models

| Command | Model | Layer | Specialty |
|---------|-------|-------|-----------|
| `/nova` | NOVA | L1 | Fast, direct, conversational |
| `/vinni` | VINNI | L2 | Observation & pattern detection |
| `/atlas` | ATLAS | L3 | Deep institutional analysis |
| `/vanta` | VANTA | L4 | Truth validation & system building |
| `/prism` | PRISM | L5 | Data quality & validation |
| `/ops` | OPS | L6 | Infrastructure & operations |

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + model selector |
| `/nova` through `/ops` | Switch AI model |
| `/models` | Show all models with inline selector |
| `/clear` | Clear conversation memory |
| `/search <query>` | Web search |
| `/help` | Show help message |

## Features

- **6 specialized AI models** — each with unique personality and expertise
- **Conversation memory** — remembers context across messages
- **Model switching** — change models mid-conversation
- **Web search** — search the internet via `/search`
- **Smart formatting** — Markdown → Telegram HTML conversion
- **Message chunking** — handles long responses by splitting intelligently
- **Markets specialty, everything scope** — financial intelligence is the focus, but handles any topic

## Architecture

```
Telegram User
     ↓
Telegraf Bot (this project)
     ↓
z-ai-web-dev-sdk (AI completions)
     ↓
GLM Large Language Model
     ↓
Model-specific system prompts (trained MATE intelligence)
     ↓
Response → Telegram HTML formatting → User
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |

## Deployment

### Local Development
```bash
npm install
export TELEGRAM_BOT_TOKEN=your_token
npm run dev
```

### Production (Render/Railway/Fly.io)
1. Push this folder to a Git repo
2. Create a new web service
3. Set `TELEGRAM_BOT_TOKEN` as an environment variable
4. Build command: `npm install`
5. Start command: `npm start`

### Docker
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY src/ ./src/
CMD ["npm", "start"]
```

## File Structure

```
mate-telegram-bot/
├── src/
│   ├── bot.js        # Main bot — commands, handlers, launch
│   ├── models.js     # 6 MATE model definitions + system prompts
│   ├── ai.js         # AI SDK integration + conversation memory
│   └── memory.js     # Conversation memory manager (LRU + sliding window)
├── .env.example      # Environment variable template
├── package.json      # Dependencies and scripts
└── README.md         # This file
```
