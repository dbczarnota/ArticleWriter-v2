// frontend/src/components/SettingsView.tsx
import { useState } from "react";
import { useDomainConfig } from "../lib/useDomainConfig";
import { SettingsNav } from "./SettingsNav";
import { DomainConfigForm } from "./DomainConfigForm";

export function SettingsView() {
  const { config, loading, saving, error, save } = useDomainConfig();
  const [activeSection, setActiveSection] = useState("podstawowe");

  if (loading) return <p style={{ color: "var(--muted)" }}>Ładowanie ustawień…</p>;
  if (!config) return <p style={{ color: "#ef4444" }}>Nie znaleziono konfiguracji domeny. Uruchom seed script.</p>;

  return (
    <div style={{ display: "flex", gap: 32, alignItems: "flex-start" }}>
      <SettingsNav activeSection={activeSection} onSelect={setActiveSection} />
      <DomainConfigForm
        initialConfig={config}
        activeSection={activeSection}
        saving={saving}
        error={error}
        onSave={save}
      />
    </div>
  );
}
