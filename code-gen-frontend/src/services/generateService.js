import { apiClient } from "./apiClient";

const SERVICE_NAME = "chat-service";
const WINDOW_SIZE = 20;

export const generateService = {
  // conversationId e trimis ca conversation_id in body, ca sa activeze RAG-ul
  // in Chat Service (care cere context de la files-service pentru aceasta
  // conversatie). Daca e null/undefined, JSON.stringify il omite si backend-ul
  // ruleaza normal, fara context.
  async streamCode(messages, conversationId, onChunk) {
    const window = messages.slice(-WINDOW_SIZE);
    return apiClient.postStream(
      SERVICE_NAME,
      "api/generate/",
      {
        messages: window.map((m) => ({ role: m.role, content: m.content })),
        conversation_id: conversationId,
      },
      onChunk
    );
  },
};
