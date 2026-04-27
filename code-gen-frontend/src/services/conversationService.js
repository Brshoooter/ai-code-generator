import { apiClient } from "./apiClient";

const SERVICE = "history-service";

export const conversationService = {
  getAll: () => apiClient.get(SERVICE, "conversations"),
  getById: (id) => apiClient.get(SERVICE, `conversations/${id}`),
  getMessages: (id) => apiClient.get(SERVICE, `conversations/${id}/messages`),
  create: (title) => apiClient.post(SERVICE, "conversations", { title }),
  addMessage: (id, role, content) =>
    apiClient.post(SERVICE, `conversations/${id}/messages`, { role, content }),
  delete: (id) => apiClient.delete(SERVICE, `conversations/${id}`),
};
