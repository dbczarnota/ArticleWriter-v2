import { useCallback } from "react";
import { useKindeAuth } from "@kinde-oss/kinde-auth-react";

const NULL_AUTH = import.meta.env.VITE_AUTH_BACKEND === "null";

export function useApi() {
  const { getToken, getOrganization, getUserOrganizations, isAuthenticated, isLoading } = useKindeAuth();

  const authReady = NULL_AUTH || (!isLoading && isAuthenticated);

  const request = useCallback(async function <T>(path: string, options: RequestInit = {}): Promise<T> {
    let orgCode = "__local_dev__";
    if (!NULL_AUTH) {
      const org = await getOrganization();
      const orgs = await getUserOrganizations();
      const orgStr = typeof org === "string" ? org : (org as any)?.orgCode;
      const orgsArr: string[] = Array.isArray(orgs) ? orgs : ((orgs as any)?.orgCodes ?? []);
      orgCode = orgStr ?? orgsArr[0] ?? "";
    }
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
  }, [getOrganization, getUserOrganizations, getToken]);

  return { request, orgCode: "", authReady };
}
