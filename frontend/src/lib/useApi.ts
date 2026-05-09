import { useCallback, useEffect, useRef } from "react";
import { useKindeAuth } from "@kinde-oss/kinde-auth-react";

const NULL_AUTH = import.meta.env.VITE_AUTH_BACKEND === "null";

interface KindeOrgPayload { orgCode?: string }
interface KindeOrgsPayload { orgCodes?: string[] }

export function useApi() {
  const { getToken, getOrganization, getUserOrganizations, isAuthenticated, isLoading } = useKindeAuth();

  const authReady = NULL_AUTH || (!isLoading && isAuthenticated);

  // Kinde's hook returns NEW function references every render. Without
  // ref-pinning, every consumer of `request` re-fires its useEffect on
  // any unrelated parent re-render, triggering avoidable re-fetches.
  const tokenRef = useRef(getToken);
  const orgRef = useRef(getOrganization);
  const orgsRef = useRef(getUserOrganizations);
  useEffect(() => {
    tokenRef.current = getToken;
    orgRef.current = getOrganization;
    orgsRef.current = getUserOrganizations;
  }, [getToken, getOrganization, getUserOrganizations]);

  const request = useCallback(async function <T>(path: string, options: RequestInit = {}): Promise<T> {
    let orgCode = "__local_dev__";
    if (!NULL_AUTH) {
      const orgRaw = await orgRef.current();
      const orgsRaw = await orgsRef.current();
      const orgStr = typeof orgRaw === "string" ? orgRaw : (orgRaw as KindeOrgPayload | null)?.orgCode;
      const orgsArr: string[] = Array.isArray(orgsRaw)
        ? orgsRaw
        : ((orgsRaw as KindeOrgsPayload | null)?.orgCodes ?? []);
      orgCode = orgStr ?? orgsArr[0] ?? "";
    }
    // FormData bodies must NOT have Content-Type set — the browser auto-sets
    // it with the right multipart boundary. Setting application/json here
    // would break multipart uploads (image, file inputs, etc.).
    const isFormData = options.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      "X-Org-Code": orgCode,
      ...(options.headers as Record<string, string> | undefined),
    };
    if (!NULL_AUTH) {
      const token = await tokenRef.current();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(path, { ...options, headers });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text}`);
    }
    return res.json() as Promise<T>;
  }, []);

  return { request, orgCode: "", authReady };
}
