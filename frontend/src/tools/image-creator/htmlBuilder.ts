export interface ImageState {
  dataUrl: string | null;
  posX: number;
  posY: number;
  scale: number;
}

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function buildHtml(
  template: string,
  textValues: Record<string, string>,
  imageStates: Record<string, ImageState>,
): string {
  return template.replace(/\{\{(TEXT|IMAGE):([^}]+)\}\}/g, (_, type, label) => {
    if (type === "TEXT") {
      return escapeHtml(textValues[label] ?? "");
    }
    const state = imageStates[label];
    if (!state?.dataUrl) return "";
    return `<img src="${state.dataUrl}" style="width:100%;height:100%;object-fit:cover;object-position:${state.posX}% ${state.posY}%;transform:scale(${state.scale});transform-origin:center;" data-slot="${label}" />`;
  });
}
