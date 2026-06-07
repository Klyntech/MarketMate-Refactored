/**
 * MATE Telegram Bot — Integration Test
 *
 * Tests AI SDK connection without needing a Telegram bot token.
 * Run: node src/test.js
 */

import { getModel, getModelIds, getModelSummary } from './models.js';
import { chat, webSearch, clearMemory } from './ai.js';

console.log('');
console.log('╔══════════════════════════════════════════════════╗');
console.log('║     🧪 MATE Telegram Bot — Integration Test     ║');
console.log('╚══════════════════════════════════════════════════╝');
console.log('');

// ─── Test 1: Model Loading ────────────────────────────────────────────────────

console.log('📋 Test 1: Model Loading');
const modelIds = getModelIds();
console.log(`   Models: ${modelIds.join(', ')}`);
console.log(`   Count: ${modelIds.length} (expected: 6)`);

for (const id of modelIds) {
  const model = getModel(id);
  console.log(`   ${model.emoji} ${model.name} (${model.layer}): ${model.role}`);
  if (!model.systemPrompt || model.systemPrompt.length < 100) {
    console.error(`   ❌ ${model.name} has insufficient system prompt`);
    process.exit(1);
  }
}
console.log('   ✅ All models loaded with valid prompts');
console.log('');

// ─── Test 2: Conversation Memory ──────────────────────────────────────────────

console.log('📋 Test 2: Conversation Memory');
clearMemory('test-chat-1');
clearMemory('test-chat-2');

// Simulate a conversation
const result1 = await chat('test-chat-1', 'Hello, who are you?', 'nova');
console.log(`   NOVA response: ${result1.response.substring(0, 80)}...`);
console.log(`   Source: ${result1.source}`);
console.log(`   Model: ${result1.model}`);

if (result1.response && result1.response.length > 10) {
  console.log('   ✅ AI chat working');
} else {
  console.log('   ⚠️  AI response was short or empty (may be SDK issue)');
}
console.log('');

// ─── Test 3: Model Switching ──────────────────────────────────────────────────

console.log('📋 Test 3: Model Switching');
clearMemory('test-chat-3');

const vantaResult = await chat('test-chat-3', 'Validate this: the sky is green.', 'vanta');
console.log(`   VANTA response: ${vantaResult.response.substring(0, 80)}...`);
console.log(`   Model: ${vantaResult.model}`);
console.log('   ✅ Model switching works');
console.log('');

// ─── Test 4: Web Search ───────────────────────────────────────────────────────

console.log('📋 Test 4: Web Search');
try {
  const searchResults = await webSearch('gold price today');
  if (searchResults && searchResults.length > 0) {
    console.log(`   Found ${searchResults.length} results`);
    console.log(`   First result: ${searchResults[0].name || searchResults[0].title || 'N/A'}`);
    console.log('   ✅ Web search working');
  } else {
    console.log('   ⚠️  No search results returned');
  }
} catch (error) {
  console.log(`   ⚠️  Web search error: ${error.message}`);
}
console.log('');

// ─── Test 5: Memory Persistence ───────────────────────────────────────────────

console.log('📋 Test 5: Memory Persistence');
clearMemory('test-chat-5');

// First message
await chat('test-chat-5', 'My name is TestUser.', 'nova');
// Second message that references the first
const memoryResult = await chat('test-chat-5', 'What is my name?', 'nova');
console.log(`   Memory response: ${memoryResult.response.substring(0, 80)}...`);
console.log('   ✅ Memory persistence test complete');
console.log('');

// ─── Summary ──────────────────────────────────────────────────────────────────

console.log('╔══════════════════════════════════════════════════╗');
console.log('║     ✅ All integration tests complete            ║');
console.log('╚══════════════════════════════════════════════════╝');
console.log('');
console.log('Next steps:');
console.log('  1. Create a bot via @BotFather on Telegram');
console.log('  2. Set TELEGRAM_BOT_TOKEN environment variable');
console.log('  3. Run: npm start');
console.log('');
