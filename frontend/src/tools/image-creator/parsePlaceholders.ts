export interface Placeholder {
  type: "TEXT" | "IMAGE";
  label: string;
}

export function parsePlaceholders(html: string): Placeholder[] {
  const seen = new Set<string>();
  const results: Placeholder[] = [];
  const regex = /\{\{(TEXT|IMAGE):([^}]+)\}\}/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(html)) !== null) {
    const key = `${match[1]}:${match[2]}`;
    if (!seen.has(key)) {
      seen.add(key);
      results.push({ type: match[1] as "TEXT" | "IMAGE", label: match[2] });
    }
  }
  return results;
}
