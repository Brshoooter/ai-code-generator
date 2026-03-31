import { createContext, useContext, useReducer, useEffect } from "react";
import { authService } from "../services/authService";

const AuthContext = createContext(null);

const initialState = {
  user: null,
  token: null,
  isAuthenticated: false,
  loading: true,
};

const authReducer = (state, action) => {
  switch (action.type) {
    case "AUTH_READY":
      return {
        ...state,
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: !!action.payload.token,
        loading: false,
      };
    case "LOGIN":
      return {
        ...state,
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
        loading: false,
      };
    case "LOGOUT":
      return {
        ...initialState,
        loading: false,
      };
    default:
      return state;
  }
};

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  useEffect(() => {
    const token = authService.getToken();
    const user = authService.getUser();

    dispatch({
      type: "AUTH_READY",
      payload: { token, user },
    });
  }, []);

  const login = async (email, password) => {
    const { token, user } = await authService.login(email, password);
    dispatch({ type: "LOGIN", payload: { token, user } });
  };

  const register = async (email, password, name) => {
    const { token, user } = await authService.register(email, password, name);
    dispatch({ type: "LOGIN", payload: { token, user } });
  };

  const logout = () => {
    authService.logout();
    dispatch({ type: "LOGOUT" });
  };

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};
