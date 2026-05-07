// Reject anything that isn't http(s). User-rendered URLs ultimately come
// from third-party RSS feeds and scraped articles; a malicious source could
// carry a `javascript:` link that would execute on click in the editor's
// browser session.
export function safeHref(url: string | null | undefined): string {
  if (!url) return "#";
  return url.startsWith("http://") || url.startsWith("https://") ? url : "#";
}
