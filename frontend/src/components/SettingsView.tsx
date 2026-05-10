import { useState } from "react";
import { useDomainConfig } from "../lib/useDomainConfig";
import { SettingsNav } from "./SettingsNav";
import { DomainConfigForm } from "./DomainConfigForm";
import { StreamsConfigSection } from "./StreamsConfigSection";
import { useT } from "../i18n";

export function SettingsView() {
  const { config, loading, saving, error, save } = useDomainConfig();
  const [activeSection, setActiveSection] = useState("podstawowe");
  const t = useT();

  if (loading) return <p style={{ color: "var(--muted)" }}>{t.settings.loading}</p>;
  if (!config) return <p style={{ color: "var(--error)" }}>{t.settings.notFound}</p>;

  return (
    <div style={{ display: "flex", gap: 32, alignItems: "flex-start" }}>
      <SettingsNav activeSection={activeSection} onSelect={setActiveSection} />
      {activeSection === "streamy" ? (
        <StreamsConfigSection config={config} saving={saving} onSave={save} />
      ) : (
        <DomainConfigForm
          initialConfig={config}
          activeSection={activeSection}
          saving={saving}
          error={error}
          onSave={save}
        />
      )}
    </div>
  );
}
