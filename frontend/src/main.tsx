import { KindeProvider } from "@kinde-oss/kinde-auth-react";
import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/tokens.css";
import App from "./App";

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

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <KindeProvider {...kindeProps}>
      <App />
    </KindeProvider>
  </React.StrictMode>
);
