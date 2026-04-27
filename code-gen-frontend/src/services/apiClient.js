import { authService } from "./authService";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080";

const buildUrl = (serviceName, path) => {
  return `${API_URL}/api/${serviceName}/${path}`;
};

// Construieste header-ele pentru fiecare request, incluzand token-ul JWT daca exista
const authHeaders = () => {
  const token = authService.getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

// Daca serverul raspunde cu 401, token-ul a expirat sau e invalid.
// Facem logout automat si redirectionam la login.
const handleUnauthorized = (response) => {
  if (response.status === 401) {
    authService.logout();
    window.location.href = "/login";
    return true;
  }
  return false;
};

export const apiClient = {
  async get(serviceName, path) {
    const response = await fetch(buildUrl(serviceName, path), {
      headers: authHeaders(),
    });

    if (handleUnauthorized(response)) return;

    if (!response.ok) {
      throw new Error(`GET ${path} failed: ${response.status}`);
    }

    return response.json();
  },

  async post(serviceName, path, body) {
    const response = await fetch(buildUrl(serviceName, path), {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
    });

    if (handleUnauthorized(response)) return;

    if (!response.ok) {
      throw new Error(`POST ${path} failed: ${response.status}`);
    }

    return response.json();
  },

  async delete(serviceName, path) {
    const response = await fetch(buildUrl(serviceName, path), {
      method: "DELETE",
      headers: authHeaders(),
    });

    if (handleUnauthorized(response)) return;

    if (!response.ok) {
      throw new Error(`DELETE ${path} failed: ${response.status}`);
    }
  },

  async postStream(serviceName, path, body, onChunk) {
    const response = await fetch(buildUrl(serviceName, path), {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
    });

    if (handleUnauthorized(response)) return;

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
