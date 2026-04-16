const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080";
const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

export const authService = {
  async login(username, password) {
    const response = await fetch(`${API_URL}/api/auth-service/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      // 422 (validare Pydantic) returneaza detail ca array de obiecte, nu string
      if (Array.isArray(error.detail)) {
        throw new Error(error.detail.map((e) => e.msg).join("; "));
      }
      throw new Error(error.detail || "Autentificare esuata.");
    }

    const data = await response.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));

    return { token: data.access_token, user: data.user };
  },

  async register(username, email, password) {
    const response = await fetch(`${API_URL}/api/auth-service/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      if (Array.isArray(error.detail)) {
        throw new Error(error.detail.map((e) => e.msg).join("; "));
      }
      throw new Error(error.detail || "Inregistrare esuata.");
    }

    const data = await response.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));

    return { token: data.access_token, user: data.user };
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  getUser() {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },

  isAuthenticated() {
    return !!localStorage.getItem(TOKEN_KEY);
  },
};
