const STORAGE_KEY = "codegen_conversations";

const loadConversations = () => {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : [];
};

const saveConversations = (conversations) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
};

export const conversationService = {
  getAll() {
    return loadConversations();
  },

  getById(id) {
    const conversations = loadConversations();
    return conversations.find((c) => c.id === id) || null;
  },

  create(title) {
    const conversations = loadConversations();
    const newConversation = {
      id: crypto.randomUUID(),
      title: title || "New Conversation",
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    conversations.unshift(newConversation);
    saveConversations(conversations);
    return newConversation;
  },

  addMessage(conversationId, role, content, files = []) {
    const conversations = loadConversations();
    const conversation = conversations.find((c) => c.id === conversationId);

    if (!conversation) return null;

    const message = {
      id: crypto.randomUUID(),
      role,
      content,
      files,
      timestamp: new Date().toISOString(),
    };

    conversation.messages.push(message);
    conversation.updatedAt = new Date().toISOString();

    if (role === "user" && conversation.messages.length === 1) {
      conversation.title = content.slice(0, 50) + (content.length > 50 ? "..." : "");
    }

    saveConversations(conversations);
    return message;
  },

  updateLastMessage(conversationId, content) {
    const conversations = loadConversations();
    const conversation = conversations.find((c) => c.id === conversationId);

    if (!conversation || conversation.messages.length === 0) return;

    const lastMessage = conversation.messages[conversation.messages.length - 1];
    lastMessage.content = content;
    conversation.updatedAt = new Date().toISOString();

    saveConversations(conversations);
  },

  delete(id) {
    const conversations = loadConversations().filter((c) => c.id !== id);
    saveConversations(conversations);
  },
};
