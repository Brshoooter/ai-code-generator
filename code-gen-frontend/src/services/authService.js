const MOCK_TOKEN = "mock-jwt-token-codegen";
const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

export const authService = {
  async login(email, password) {
    await new Promise((resolve) => setTimeout(resolve, 500));

    if (!email || !password) {
      throw new Error("Email and password are required");
    }

    const user = { email, name: email.split("@")[0] };
    localStorage.setItem(TOKEN_KEY, MOCK_TOKEN);
    localStorage.setItem(USER_KEY, JSON.stringify(user));

    return { token: MOCK_TOKEN, user };
  },

  async register(email, password, name) {
    await new Promise((resolve) => setTimeout(resolve, 500));

    if (!email || !password || !name) {
      throw new Error("All fields are required");
    }

    const user = { email, name };
    localStorage.setItem(TOKEN_KEY, MOCK_TOKEN);
    localStorage.setItem(USER_KEY, JSON.stringify(user));

    return { token: MOCK_TOKEN, user };
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
