import { useState } from "react";
import { useStreamSubscriptions } from "../lib/useStreamSubscriptions";
import { useT } from "../i18n";
import type { DomainConfigData } from "../types";

const EMPTY_FORM = {
  name: "",
  stream_url: "",
  stream_type: "radio",
  url_refresh_url: "",
  url_refresh_field: "url",
  chunk_duration_seconds: 180,
};

interface Props {
  config: DomainConfigData;
  saving: boolean;
  onSave: (updated: DomainConfigData) => Promise<void>;
}

export function StreamsConfigSection({ config, saving: domainSaving, onSave }: Props) {
  const t = useT();
  const { subscriptions, loading, create, remove, start, stop } = useStreamSubscriptions();
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState(false);
  const [toggling, setToggling] = useState<Set<string>>(new Set());
  const [retentionDays, setRetentionDays] = useState(config.stream_retention_days);
  const [retentionSavedMsg, setRetentionSavedMsg] = useState(false);

  async function saveRetention() {
    if (retentionDays === config.stream_retention_days) return;
    try {
      await onSave({ ...config, stream_retention_days: retentionDays });
      setRetentionSavedMsg(true);
      setTimeout(() => setRetentionSavedMsg(false), 2000);
    } catch (err) {
      console.error("StreamsConfigSection: retention save failed", err);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "6px 8px",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    fontSize: 13,
    color: "var(--text)",
    background: "var(--white)",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 12,
    color: "var(--muted)",
    display: "block",
    marginBottom: 3,
  };

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.stream_url.trim()) return;
    setSaving(true);
    try {
      await create({
        name: form.name.trim(),
        stream_url: form.stream_url.trim(),
        stream_type: form.stream_type,
        url_refresh_url: form.url_refresh_url.trim() || undefined,
        url_refresh_field: form.url_refresh_field.trim() || "url",
        chunk_duration_seconds: form.chunk_duration_seconds,
      });
      setForm(EMPTY_FORM);
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2000);
    } catch (err) {
      console.error("StreamsConfigSection: create failed", err);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(id: string, isActive: boolean) {
    setToggling((prev) => new Set(prev).add(id));
    try {
      if (isActive) {
        await stop(id);
      } else {
        await start(id);
      }
    } catch (err) {
      console.error("StreamsConfigSection: toggle failed", err);
    } finally {
      setToggling((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
        {t.streams.config.sectionStreams}
      </h2>
      <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 24 }}>
        {t.streams.config.streamsHint}
      </p>

      {/* Retention */}
      <div style={{ marginBottom: 24, padding: 12, border: "1px solid var(--border)", borderRadius: "var(--radius)", background: "var(--white)" }}>
        <label style={labelStyle}>
          {t.streams.config.retentionDays}
        </label>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="number"
            min={1}
            max={365}
            value={retentionDays}
            onChange={(e) => setRetentionDays(+e.target.value)}
            style={{ ...inputStyle, width: 100 }}
            disabled={domainSaving}
          />
          <button
            type="button"
            onClick={saveRetention}
            disabled={domainSaving || retentionDays === config.stream_retention_days}
            style={{
              padding: "6px 14px",
              background: "var(--accent)",
              color: "var(--white)",
              border: "none",
              borderRadius: "var(--radius)",
              fontSize: 13,
              cursor: (domainSaving || retentionDays === config.stream_retention_days) ? "default" : "pointer",
              opacity: (domainSaving || retentionDays === config.stream_retention_days) ? 0.5 : 1,
            }}
          >
            {domainSaving ? t.streams.config.saving : t.streams.config.save}
          </button>
          {retentionSavedMsg && (
            <span style={{ fontSize: 12, color: "var(--success-fg)" }}>{t.streams.config.saved}</span>
          )}
        </div>
        <p style={{ fontSize: 11, color: "var(--muted)", marginTop: 6, marginBottom: 0 }}>
          {t.streams.config.retentionHint}
        </p>
      </div>

      {/* Existing subscriptions */}
      {!loading && subscriptions.length > 0 && (
        <div style={{ marginBottom: 24, display: "flex", flexDirection: "column", gap: 8 }}>
          {subscriptions.map((sub) => {
            const isActive = sub.status === "active";
            const isToggling = toggling.has(sub.id);
            return (
              <div
                key={sub.id}
                style={{
                  padding: "10px 14px",
                  border: `1px solid ${isActive ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.25)"}`,
                  borderRadius: "var(--radius)",
                  background: isActive ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.05)",
                  transition: "background 0.2s, border-color 0.2s",
                }}
              >
                {/* Top row: name + type badge */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{sub.name}</span>
                  <span
                    style={{
                      fontSize: 10,
                      color: "var(--muted)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      background: "var(--bg)",
                      border: "1px solid var(--border)",
                      borderRadius: 3,
                      padding: "1px 5px",
                    }}
                  >
                    {sub.stream_type}
                  </span>
                </div>

                {/* URL row */}
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--muted)",
                    fontFamily: "ui-monospace, Menlo, monospace",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    marginBottom: 10,
                  }}
                >
                  {sub.stream_url}
                </div>

                {/* Bottom row: toggle + delete */}
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      cursor: isToggling ? "default" : "pointer",
                      opacity: isToggling ? 0.5 : 1,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isActive}
                      disabled={isToggling}
                      onChange={() => void handleToggle(sub.id, isActive)}
                      style={{ width: 15, height: 15, cursor: isToggling ? "default" : "pointer" }}
                    />
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: isActive ? "rgb(22,163,74)" : "rgb(220,38,38)",
                      }}
                    >
                      {isActive ? t.streams.subscription.live : t.streams.subscription.stopped}
                    </span>
                  </label>

                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm(t.streams.subscription.confirmDelete)) {
                        void remove(sub.id);
                      }
                    }}
                    style={{
                      fontSize: 11,
                      color: "var(--muted)",
                      background: "none",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius)",
                      padding: "2px 10px",
                      cursor: "pointer",
                    }}
                  >
                    {t.streams.config.removeStream}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add stream form */}
      <form onSubmit={(e) => void handleAdd(e)}>
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: 16,
            background: "var(--bg)",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>{t.streams.config.streamName}</label>
              <input
                style={inputStyle}
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder={t.streams.config.streamNamePlaceholder}
              />
            </div>
            <div>
              <label style={labelStyle}>{t.streams.config.streamType}</label>
              <select
                style={inputStyle}
                value={form.stream_type}
                onChange={(e) => setForm((f) => ({ ...f, stream_type: e.target.value }))}
              >
                <option value="radio">radio</option>
                <option value="tv">tv</option>
              </select>
            </div>
          </div>
          <div>
            <label style={labelStyle}>{t.streams.config.streamUrl}</label>
            <input
              style={inputStyle}
              value={form.stream_url}
              onChange={(e) => setForm((f) => ({ ...f, stream_url: e.target.value }))}
              placeholder={t.streams.config.streamUrlPlaceholder}
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12 }}>
            <div>
              <label style={labelStyle}>{t.streams.config.urlRefreshUrl}</label>
              <input
                style={inputStyle}
                value={form.url_refresh_url}
                onChange={(e) => setForm((f) => ({ ...f, url_refresh_url: e.target.value }))}
                placeholder={t.streams.config.urlRefreshUrlPlaceholder}
              />
            </div>
            <div>
              <label style={labelStyle}>{t.streams.config.urlRefreshField}</label>
              <input
                style={{ ...inputStyle, width: 100 }}
                value={form.url_refresh_field}
                onChange={(e) => setForm((f) => ({ ...f, url_refresh_field: e.target.value }))}
                placeholder="url"
              />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
            <div>
              <label style={labelStyle}>{t.streams.config.chunkDuration}</label>
              <input
                type="number"
                style={{ ...inputStyle, width: 100 }}
                value={form.chunk_duration_seconds}
                min={30}
                max={600}
                onChange={(e) =>
                  setForm((f) => ({ ...f, chunk_duration_seconds: Number(e.target.value) }))
                }
              />
            </div>
            <button
              type="submit"
              disabled={saving || !form.name.trim() || !form.stream_url.trim()}
              style={{
                padding: "7px 18px",
                background: "var(--accent)",
                color: "var(--white)",
                border: "none",
                borderRadius: "var(--radius)",
                fontSize: 13,
                fontWeight: 500,
                cursor: saving ? "default" : "pointer",
                opacity: saving || !form.name.trim() || !form.stream_url.trim() ? 0.6 : 1,
              }}
            >
              {saving ? t.streams.config.saving : t.streams.config.addStream}
            </button>
            {savedMsg && (
              <span style={{ fontSize: 12, color: "var(--success-fg)" }}>
                {t.streams.config.saved}
              </span>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
