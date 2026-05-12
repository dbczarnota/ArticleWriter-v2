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

  it("renders all major section headings in PL", async () => {
    await renderLanding("pl");
    expect(screen.getByText(/pisz /i)).toBeInTheDocument();
    expect(screen.getByText(/cały newsroom w jednym miejscu/i)).toBeInTheDocument();
    expect(screen.getByText(/wszystko, czego potrzebuje/i)).toBeInTheDocument();
    expect(screen.getByText(/zawsze wiesz, co jest gorące/i)).toBeInTheDocument();
    expect(screen.getByText(/słuchamy mediów za ciebie/i)).toBeInTheDocument();
    expect(screen.getByText(/wystarczy ślad/i)).toBeInTheDocument();
    expect(screen.getByText(/zbudowane dla redakcji/i)).toBeInTheDocument();
    expect(screen.getByText(/nigdy nie kopiujemy/i)).toBeInTheDocument();
    expect(screen.getByText(/gotowy pisać szybciej/i)).toBeInTheDocument();
  });

  it("renders all major section headings in EN", async () => {
    await renderLanding("en");
    expect(screen.getAllByText(/write /i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/your whole newsroom in one place/i)).toBeInTheDocument();
    expect(screen.getByText(/everything a modern newsroom needs/i)).toBeInTheDocument();
    expect(screen.getByText(/we never copy/i)).toBeInTheDocument();
  });

  it("toggles language from PL to EN via lang toggle", async () => {
    await renderLanding("pl");
    expect(screen.queryByText(/your whole newsroom in one place/i)).not.toBeInTheDocument();

    const enBtn = screen.getByRole("button", { name: "EN" });
    await userEvent.click(enBtn);

    expect(screen.getByText(/your whole newsroom in one place/i)).toBeInTheDocument();
    expect(screen.queryByText(/cały newsroom w jednym miejscu/i)).not.toBeInTheDocument();
  });

  it("clicking primary CTA in hero calls login()", async () => {
    await renderLanding("pl");
    const ctas = screen.getAllByRole("button", { name: /wypróbuj za darmo/i });
    expect(ctas.length).toBeGreaterThanOrEqual(1);
    await userEvent.click(ctas[0]);
    expect(mockLogin).toHaveBeenCalledOnce();
  });

  it("clicking nav 'Zaloguj się' calls login()", async () => {
    await renderLanding("pl");
    const signin = screen.getByRole("button", { name: /zaloguj się/i });
    await userEvent.click(signin);
    expect(mockLogin).toHaveBeenCalledOnce();
  });
});
