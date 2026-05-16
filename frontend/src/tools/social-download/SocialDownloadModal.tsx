import { useState } from "react";
import { useApi } from "../../lib/useApi";
import { useT, useLang } from "../../i18n";
import { CopyIcon, CheckIcon, DownloadIcon } from "../../components/ui/icons";

export type SocialPlatform = "instagram" | "x";

interface SocialDownloadModalProps {
  platform: SocialPlatform;
  onClose: () => void;
}

interface FetchResult {
  media_url: string;
  media_type: string;
  description?: string; // instagram
  text?: string; // x
  author?: string; // x
  comments: string[];
}

const HEADER_LABEL: Record<SocialPlatform, { pl: string; en: string }> = {
  instagram: { pl: "Ściągnij post z Instagrama", en: "Download Instagram post" },
  x: { pl: "Ściągnij post z X.com", en: "Download X.com post" },
};

const URL_PLACEHOLDER: Record<SocialPlatform, string> = {
  instagram: "https://www.instagram.com/p/...",
  x: "https://x.com/.../status/...",
};

const URL_REGEX: Record<SocialPlatform, RegExp> = {
  instagram: /^https?:\/\/(www\.)?instagram\.com\/(p|reel|reels|tv)\/[\w-]+/i,
  x: /^https?:\/\/(www\.)?(x\.com|twitter\.com)\/[^/]+\/status\/\d+/i,
};

function friendlyError(
  raw: string,
  platform: SocialPlatform,
  lang: string,
): string {
  // Server returned 422 with a parse/validation message → translate.
  if (/^422\b/.test(raw) || /shortcode|invalid|parse|tweet url/i.test(raw)) {
    if (platform === "instagram") {
      return lang === "pl"
        ? "To nie wygląda na link do posta na Instagramie. Wklej URL postaci https://www.instagram.com/p/... (lub /reel/...)."
        : "That doesn't look like an Instagram post link. Paste a URL like https://www.instagram.com/p/... (or /reel/...).";
    }
    return lang === "pl"
      ? "To nie wygląda na link do posta na X.com. Wklej URL postaci https://x.com/<użytkownik>/status/<id>."
      : "That doesn't look like an X.com post link. Paste a URL like https://x.com/<user>/status/<id>.";
  }
  // Apify token missing
  if (/APIFY_API_TOKEN/i.test(raw)) {
    return lang === "pl"
      ? "Serwis pobierający (Apify) nie jest skonfigurowany po stronie serwera. Skontaktuj się z administratorem."
      : "The fetcher service (Apify) is not configured on the server. Contact your admin.";
  }
  // Generic fallback — keep the raw message but strip leading status code
  return raw.replace(/^\d{3}:\s*/, "");
}

export function SocialDownloadModal({ platform, onClose }: SocialDownloadModalProps) {
  const t = useT();
  const { lang } = useLang();
  const { request, downloadFile } = useApi();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FetchResult | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [downloadingMedia, setDownloadingMedia] = useState(false);

  async function handleFetch() {
    const trimmed = url.trim();
    if (!trimmed) return;
    // Quick client-side check — saves a round-trip and gives the same friendly
    // message immediately instead of waiting for the 422.
    if (!URL_REGEX[platform].test(trimmed)) {
      setError(friendlyError("422", platform, lang));
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await request<FetchResult>(`/v2/tools/social-download/${platform}`, {
        method: "POST",
        body: JSON.stringify({ url: trimmed }),
      });
      setResult(data);
    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : String(e);
      setError(friendlyError(raw, platform, lang));
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1500);
    } catch {
      // ignore
    }
  }

  async function handleDownloadMedia() {
    if (!result?.media_url) return;
    setDownloadingMedia(true);
    try {
      const ext = result.media_type.startsWith("video") ? "mp4" : "jpg";
      const filename = `${platform}-${Date.now()}.${ext}`;
      const proxied = `/v2/download_media?url=${encodeURIComponent(result.media_url)}`;
      await downloadFile(proxied, filename);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloadingMedia(false);
    }
  }

  const headerText = HEADER_LABEL[platform][lang as "pl" | "en"] ?? HEADER_LABEL[platform].pl;
  const captionText = platform === "instagram" ? result?.description : result?.text;
  const captionLabel = lang === "pl"
    ? (platform === "instagram" ? "Opis" : "Treść posta")
    : (platform === "instagram" ? "Description" : "Post text");
  const commentsLabel = lang === "pl"
    ? (platform === "instagram" ? "Komentarze" : "Odpowiedzi")
    : (platform === "instagram" ? "Comments" : "Replies");

  return (
    <>
      <header
        style={{
          padding: "14px 18px",
          borderBottom: "1px solid var(--card-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexShrink: 0,
        }}
      >
        <h3 style={{ margin: 0, fontSize: 16, color: "var(--ink)", fontWeight: 800, letterSpacing: "-.025em" }}>
          {headerText}
          {result?.author && <span style={{ marginLeft: 8, color: "var(--ink-subtle)", fontWeight: 500 }}>@{result.author}</span>}
        </h3>
        <button
          onClick={onClose}
          aria-label={t.imageCreator.close}
          style={{
            width: 28,
            height: 28,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
            background: "transparent",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--radius)",
            cursor: "pointer",
            color: "var(--ink-subtle)",
            lineHeight: 0,
            flexShrink: 0,
          }}
        >
          ×
        </button>
      </header>

      <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--card-border)", display: "flex", gap: 8, flexShrink: 0 }}>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={URL_PLACEHOLDER[platform]}
          onKeyDown={(e) => { if (e.key === "Enter") handleFetch(); }}
          disabled={loading}
          style={{
            flex: 1,
            minWidth: 0,
            padding: "8px 10px",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--radius)",
            background: "var(--card-bg)",
            color: "var(--ink)",
            fontSize: 13,
            fontFamily: "inherit",
            boxSizing: "border-box",
          }}
        />
        <button
          onClick={handleFetch}
          disabled={loading || !url.trim()}
          style={{
            padding: "8px 18px",
            background: "var(--accent)",
            color: "white",
            border: "none",
            borderRadius: "var(--radius)",
            fontSize: 13,
            fontWeight: 600,
            cursor: loading || !url.trim() ? "not-allowed" : "pointer",
            opacity: loading || !url.trim() ? 0.6 : 1,
            fontFamily: "inherit",
            flexShrink: 0,
          }}
        >
          {loading ? (lang === "pl" ? "Pobieram…" : "Fetching…") : (lang === "pl" ? "Pobierz" : "Fetch")}
        </button>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "20px 24px", background: "var(--canvas-bg)" }}>
        {error && (
          <p style={{ color: "var(--error)", fontSize: 13, marginBottom: 16 }}>
            {error}
          </p>
        )}

        {!result && !error && !loading && (
          <p style={{ color: "var(--ink-subtle)", fontSize: 13, fontStyle: "italic" }}>
            {lang === "pl"
              ? "Wklej link i kliknij \"Pobierz\". Pobierzemy media, opis i komentarze — nic nie zapisujemy."
              : "Paste a link and click \"Fetch\". We'll pull the media, caption and comments — nothing is stored."}
          </p>
        )}

        {result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {result.media_url && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "center", background: "var(--card-bg)", border: "1px solid var(--card-border)", borderRadius: "var(--radius)", padding: 8 }}>
                  {result.media_type.startsWith("video") ? (
                    <video
                      src={result.media_url}
                      controls
                      style={{ maxWidth: "100%", maxHeight: 380, borderRadius: 4 }}
                    />
                  ) : (
                    <img
                      src={result.media_url}
                      alt=""
                      style={{ maxWidth: "100%", maxHeight: 380, borderRadius: 4 }}
                    />
                  )}
                </div>
                <button
                  onClick={handleDownloadMedia}
                  disabled={downloadingMedia}
                  style={{
                    alignSelf: "flex-start",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 12px",
                    background: "var(--accent)",
                    color: "white",
                    border: "none",
                    borderRadius: "var(--radius)",
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: downloadingMedia ? "not-allowed" : "pointer",
                    opacity: downloadingMedia ? 0.6 : 1,
                    fontFamily: "inherit",
                  }}
                >
                  <DownloadIcon />
                  {downloadingMedia
                    ? (lang === "pl" ? "Pobieram…" : "Downloading…")
                    : (lang === "pl"
                      ? (result.media_type.startsWith("video") ? "Pobierz wideo" : "Pobierz zdjęcie")
                      : (result.media_type.startsWith("video") ? "Download video" : "Download image"))}
                </button>
              </div>
            )}

            {captionText && (
              <Section
                label={captionLabel}
                onCopy={() => handleCopy(captionText, "caption")}
                copied={copiedKey === "caption"}
              >
                <p style={{ margin: 0, fontSize: 13, color: "var(--ink)", lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
                  {captionText}
                </p>
              </Section>
            )}

            {result.comments && result.comments.length > 0 && (
              <Section
                label={`${commentsLabel} (${result.comments.length})`}
                onCopy={() => handleCopy(result.comments.join("\n"), "comments-all")}
                copied={copiedKey === "comments-all"}
                copyTitle={lang === "pl" ? "Kopiuj wszystkie" : "Copy all"}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {result.comments.map((c, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        gap: 8,
                        alignItems: "flex-start",
                        padding: "6px 10px",
                        background: "var(--canvas-bg)",
                        border: "1px solid var(--card-border)",
                        borderRadius: "var(--radius)",
                      }}
                    >
                      <span style={{ flex: 1, minWidth: 0, fontSize: 12, color: "var(--ink)", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                        {c}
                      </span>
                      <button
                        onClick={() => handleCopy(c, `c-${i}`)}
                        title={lang === "pl" ? "Kopiuj" : "Copy"}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 22,
                          height: 22,
                          padding: 0,
                          background: "transparent",
                          border: "1px solid var(--card-border)",
                          borderRadius: "var(--radius)",
                          color: copiedKey === `c-${i}` ? "var(--success, #16a34a)" : "var(--ink-subtle)",
                          cursor: "pointer",
                          flexShrink: 0,
                          lineHeight: 0,
                        }}
                      >
                        {copiedKey === `c-${i}` ? <CheckIcon width={11} height={11} /> : <CopyIcon width={11} height={11} />}
                      </button>
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </div>
        )}
      </div>
    </>
  );
}

interface SectionProps {
  label: string;
  onCopy: () => void;
  copied: boolean;
  copyTitle?: string;
  children: React.ReactNode;
}

function Section({ label, onCopy, copied, copyTitle, children }: SectionProps) {
  const { lang } = useLang();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--ink-subtle)" }}>
          {label}
        </span>
        <button
          onClick={onCopy}
          title={copyTitle ?? (lang === "pl" ? "Kopiuj do schowka" : "Copy to clipboard")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 24,
            height: 24,
            padding: 0,
            background: "transparent",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--radius)",
            color: copied ? "var(--success, #16a34a)" : "var(--ink-subtle)",
            cursor: "pointer",
            lineHeight: 0,
          }}
        >
          {copied ? <CheckIcon width={12} height={12} /> : <CopyIcon width={12} height={12} />}
        </button>
      </div>
      <div style={{ padding: "10px 12px", background: "var(--card-bg)", border: "1px solid var(--card-border)", borderRadius: "var(--radius)" }}>
        {children}
      </div>
    </div>
  );
}
