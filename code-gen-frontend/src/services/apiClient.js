const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080";

const buildUrl = (serviceName, path) => {
  return `${API_URL}/api/${serviceName}/${path}`;
};

export const apiClient = {
  async get(serviceName, path) {
    const response = await fetch(buildUrl(serviceName, path));

    if (!response.ok) {
      throw new Error(`GET ${path} failed: ${response.status}`);
    }

    return response.json();
  },

  async post(serviceName, path, body) {
    const response = await fetch(buildUrl(serviceName, path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`POST ${path} failed: ${response.status}`);
    }

    return response.json();
  },

  async postStream(serviceName, path, body, onChunk) {
    const response = await fetch(buildUrl(serviceName, path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`POST stream ${path} failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      onChunk(chunk);
    }
  },
};
