/**
 * Conversation Memory Manager
 *
 * Tracks conversation history per Telegram chat with sliding window eviction.
 * Each chat stores up to maxTurns message pairs (user + assistant).
 * LRU eviction when maxChats is exceeded.
 */

class ConversationMemory {
  constructor(maxTurnsPerChat = 20, maxChats = 500) {
    this.maxTurns = maxTurnsPerChat;
    this.maxChats = maxChats;
    this.memory = new Map(); // chatId -> [{ role, content }, ...]
    this.accessOrder = [];   // LRU tracking
  }

  /**
   * Add a turn to the conversation history
   */
  addTurn(chatId, role, content) {
    if (!chatId) return;

    if (!this.memory.has(chatId)) {
      // Evict oldest if at capacity
      if (this.accessOrder.length >= this.maxChats) {
        const oldest = this.accessOrder.shift();
        this.memory.delete(oldest);
      }
      this.memory.set(chatId, []);
    }

    const history = this.memory.get(chatId);
    history.push({ role, content });

    // Sliding window: keep only last N turns
    if (history.length > this.maxTurns) {
      this.memory.set(chatId, history.slice(-this.maxTurns));
    }

    // Update LRU order
    this._touch(chatId);
  }

  /**
   * Get conversation history for a chat
   */
  getHistory(chatId) {
    this._touch(chatId);
    return this.memory.get(chatId) || [];
  }

  /**
   * Clear conversation history for a chat
   */
  clear(chatId) {
    this.memory.delete(chatId);
    this.accessOrder = this.accessOrder.filter(id => id !== chatId);
  }

  /**
   * Get the number of active conversations
   */
  get activeConversations() {
    return this.memory.size;
  }

  /**
   * Update LRU access order
   */
  _touch(chatId) {
    this.accessOrder = this.accessOrder.filter(id => id !== chatId);
    this.accessOrder.push(chatId);
  }
}

// Singleton instance
const memory = new ConversationMemory(20, 500);

export default memory;
export { ConversationMemory };
