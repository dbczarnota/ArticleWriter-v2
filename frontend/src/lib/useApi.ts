import { useKindeAuth } from "@kinde-oss/kinde-auth-react";

const NULL_AUTH = import.meta.env.VITE_AUTH_BACKEND === "null";

export function useApi() {
  const { getToken, user } = useKindeAuth();

  const orgCode = NULL_AUTH ? "__local_dev__" : (user?.org_codes?.[0] ?? "");

  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Org-Code": orgCode,
      ...(options.headers as Record<string, string> | undefined),
    };
    if (!NULL_AUTH) {
      const token = await getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(path, { ...options, headers });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text}`);
    }
    return res.json() as Promise<T>;
  }

  return { request, orgCode };
}
