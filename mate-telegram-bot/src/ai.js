/**
 * AI Engine — Connects to z-ai-web-dev-sdk for MATE completions
 *
 * Provides:
 * - Chat completions with model-specific system prompts
 * - Conversation memory integration
 * - Web search capability
 * - Error handling with graceful fallbacks
 */

import ZAI from 'z-ai-web-dev-sdk';
import { getModel } from './models.js';
import memory from './memory.js';

let zaiInstance = null;

/**
 * Initialize the AI SDK
 */
async function getAI() {
  if (!zaiInstance) {
    zaiInstance = await ZAI.create();
  }
  return zaiInstance;
}

/**
 * Send a message to a MATE model and get a response
 *
 * @param {string} chatId - Telegram chat ID for conversation memory
 * @param {string} userMessage - The user's message
 * @param {string} modelId - The model ID (nova, atlas, vanta, prism, vinni, ops)
 * @returns {Promise<{response: string, source: string, model: string}>}
 */
export async function chat(chatId, userMessage, modelId = 'nova') {
  const model = getModel(modelId);

  try {
    const zai = await getAI();

    // Build messages array with conversation history
    const messages = [
      { role: 'system', content: model.systemPrompt },
    ];

    // Add conversation history
    const history = memory.getHistory(chatId);
    for (const turn of history) {
      messages.push({ role: turn.role, content: turn.content });
    }

    // Add current user message
    messages.push({ role: 'user', content: userMessage });

    const completion = await zai.chat.completions.create({
      messages,
      temperature: 0.6,
      max_tokens: 2048,
    });

    const response = completion.choices?.[0]?.message?.content;

    if (response) {
      // Store in conversation memory
      memory.addTurn(chatId, 'user', userMessage);
      memory.addTurn(chatId, 'assistant', response);

      return {
        response,
        source: 'ai',
        model: model.name,
      };
    }

    return {
      response: "I couldn't generate a response. Please try again.",
      source: 'empty',
      model: model.name,
    };

  } catch (error) {
    console.error(`[MATE AI Error] Model: ${model.name}, Error:`, error.message);

    return {
      response: `I'm experiencing connectivity issues right now. Please try again in a moment.`,
      source: 'error',
      model: model.name,
    };
  }
}

/**
 * Perform a web search via the AI SDK
 *
 * @param {string} query - Search query
 * @returns {Promise<Array>} Search results
 */
export async function webSearch(query) {
  try {
    const zai = await getAI();
    const results = await zai.functions.invoke('web_search', {
      query,
      num: 5,
    });
    return results || [];
  } catch (error) {
    console.error('[MATE Web Search Error]', error.message);
    return [];
  }
}

/**
 * Get the current status of the AI engine
 */
export function getStatus() {
  return {
    initialized: zaiInstance !== null,
    activeConversations: memory.activeConversations,
  };
}

/**
 * Clear conversation memory for a specific chat
 */
export function clearMemory(chatId) {
  memory.clear(chatId);
}
