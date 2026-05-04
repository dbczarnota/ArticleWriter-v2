import { createContext, useContext } from "react";
import type { Translations } from "./types";
import { pl } from "./pl";
import { en } from "./en";

export type Lang = "pl" | "en";

const LANGS: Record<Lang, Translations> = { pl, en };

const STORAGE_KEY = "hf_lang";

function getInitialLang(): Lang {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "en" ? "en" : "pl";
}

interface LangContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Translations;
}

export const LangContext = createContext<LangContextValue>({
  lang: "pl",
  setLang: () => {},
  t: pl,
});

export function useLang() {
  return useContext(LangContext);
}

export function useT(): Translations {
  return useContext(LangContext).t;
}

export { pl, en, LANGS, STORAGE_KEY, getInitialLang };
export type { Translations };
