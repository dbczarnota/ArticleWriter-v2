import "@fontsource-variable/inter/wght.css";
import { KindeProvider } from "@kinde-oss/kinde-auth-react";
import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles/tokens.css";
import "./styles/landing.css";
import App from "./App";
import { LangContext, LANGS, STORAGE_KEY, getInitialLang } from "./i18n";
import type { Lang } from "./i18n";

const NULL_AUTH = import.meta.env.VITE_AUTH_BACKEND === "null";

const kindeProps = NULL_AUTH
  ? {
      clientId: "null",
      domain: "https://null.kinde.com",
      redirectUri: window.location.origin,
      logoutUri: window.location.origin,
    }
  : {
      clientId: import.meta.env.VITE_KINDE_CLIENT_ID,
      domain: import.meta.env.VITE_KINDE_DOMAIN,
      redirectUri: window.location.origin,
      logoutUri: window.location.origin,
      audience: import.meta.env.VITE_KINDE_AUDIENCE,
    };

function Root() {
  const [lang, setLangState] = useState<Lang>(getInitialLang);

  function setLang(l: Lang) {
    setLangState(l);
    localStorage.setItem(STORAGE_KEY, l);
  }

  return (
    <LangContext.Provider value={{ lang, setLang, t: LANGS[lang] }}>
      <KindeProvider {...kindeProps}>
        <App />
      </KindeProvider>
    </LangContext.Provider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);


