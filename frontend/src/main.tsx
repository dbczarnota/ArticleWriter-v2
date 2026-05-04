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
      clientId: "5167f046636b4fa4a04c157b7105b9fc",
      domain: "https://scripts.kinde.com",
      redirectUri: window.location.origin,
      logoutUri: window.location.origin,
      audience: "articlewriter-api",
    };

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <KindeProvider {...kindeProps}>
      <App />
    </KindeProvider>
  </React.StrictMode>
);
