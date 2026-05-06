import { useState } from "react";

type DiscoveryView = "topics" | "items" | "feeds";

export function DiscoveryHub() {
  const [view, setView] = useState<DiscoveryView>("topics");
  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ margin: 0 }}>Discovery</h2>
      <div style={{ display: "flex", gap: 8, margin: "16px 0" }}>
        <button onClick={() => setView("topics")} disabled={view === "topics"}>Tematy</button>
        <button onClick={() => setView("items")} disabled={view === "items"}>Itemy</button>
        <button onClick={() => setView("feeds")} disabled={view === "feeds"}>Feedy</button>
      </div>
      <div style={{ color: "var(--muted)" }}>Current view: {view}</div>
    </div>
  );
}
