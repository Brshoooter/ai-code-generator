import { apiClient } from "./apiClient";

const SERVICE_NAME = "chat-service";
const WINDOW_SIZE = 20;

export const generateService = {
  async streamCode(messages, onChunk) {
    const window = messages.slice(-WINDOW_SIZE);
    return apiClient.postStream(
      SERVICE_NAME,
      "api/generate/",
      { messages: window.map((m) => ({ role: m.role, content: m.content })) },
      onChunk
    );
  },
};
