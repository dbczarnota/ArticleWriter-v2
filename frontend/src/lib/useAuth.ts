import { useKindeAuth } from "@kinde-oss/kinde-auth-react";

export function useAuth() {
  const { isAuthenticated, isLoading, user, login, logout, getToken } = useKindeAuth();
  return { isAuthenticated, isLoading, user, login, logout, getToken };
}
