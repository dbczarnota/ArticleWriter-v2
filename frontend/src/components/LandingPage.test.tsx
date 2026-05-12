import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { LangContext, LANGS, type Lang } from "../i18n";

const mockLogin = vi.fn();
vi.mock("../lib/useAuth", () => ({
  useAuth: () => ({
    login: mockLogin, logout: vi.fn(),
    isAuthenticated: false, isLoading: false, user: null,
  }),
}));

function TestLangProvider({ children, initial = "pl" as Lang }: { children: React.ReactNode; initial?: Lang }) {
  const [lang, setLang] = useState<Lang>(initial);
  return (
    <LangContext.Provider value={{ lang, setLang, t: LANGS[lang] }}>
      {children}
    </LangContext.Provider>
  );
}

async function renderLanding(initial: Lang = "pl") {
  const { LandingPage } = await import("./LandingPage");
  return render(
    <TestLangProvider initial={initial}>
      <LandingPage />
    </TestLangProvider>
  );
}

describe("LandingPage", () => {
  beforeEach(() => mockLogin.mockClear());

  it("renders Polish hero headline by default", async () => {
    await renderLanding("pl");
    expect(screen.getByText(/szybciej/i)).toBeInTheDocument();
  });

  it("clicking nav 'Zaloguj się' calls login()", async () => {
    await renderLanding("pl");
    const signin = screen.getByRole("button", { name: /zaloguj się/i });
    await userEvent.click(signin);
    expect(mockLogin).toHaveBeenCalledOnce();
  });
});
