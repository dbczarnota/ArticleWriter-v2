import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { renderHook, act } from "@testing-library/react";

vi.mock("@kinde-oss/kinde-auth-react", () => ({
  useKindeAuth: () => ({
    getToken: vi.fn(),
    getOrganization: vi.fn(),
    getUserOrganizations: vi.fn(),
    isAuthenticated: true,
    isLoading: false,
  }),
}));

// NULL_AUTH is captured at module evaluation, so we must stub the env BEFORE
// importing useApi. We import the module dynamically after the stub.
let useApi: typeof import("./useApi").useApi;

beforeAll(async () => {
  vi.stubEnv("VITE_AUTH_BACKEND", "null");
  vi.resetModules();
  ({ useApi } = await import("./useApi"));
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useApi (NULL_AUTH)", () => {
  it("returns authReady=true and a request function without calling Kinde", async () => {
    const { result } = renderHook(() => useApi());
    expect(result.current.authReady).toBe(true);
    expect(typeof result.current.request).toBe("function");

    globalThis.fetch = vi.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
    await act(async () => {
      const res = await result.current.request<{ ok: boolean }>("/v2/health");
      expect(res.ok).toBe(true);
    });
    const call = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    const headers = call[1].headers as Record<string, string>;
    expect(headers["X-Org-Code"]).toBe("__local_dev__");
    expect(headers["Authorization"]).toBeUndefined();
  });

  it("throws when response is not ok", async () => {
    const { result } = renderHook(() => useApi());
    globalThis.fetch = vi.fn().mockResolvedValue(new Response("nope", { status: 500 }));
    await expect(result.current.request("/v2/x")).rejects.toThrow(/500/);
  });

  it("returns a stable `request` reference across re-renders", () => {
    // The whole motivation for the ref pattern in useApi is to keep
    // `request` identity-stable so consumer useEffect([request]) doesn't
    // re-fire on unrelated parent re-renders. Lock that contract.
    const { result, rerender } = renderHook(() => useApi());
    const first = result.current.request;
    rerender();
    rerender();
    expect(result.current.request).toBe(first);
  });
});
