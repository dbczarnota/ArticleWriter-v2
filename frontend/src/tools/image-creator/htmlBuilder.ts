export interface ImageState {
  dataUrl: string | null;
  /** Pan offset from slot center, in pixels (template-space). */
  panX: number;
  panY: number;
  /** Zoom factor relative to the cover-fit size. 1 = exact cover. */
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
    const pct = state.scale * 100;
    // Wrapper provides a position:relative container so the img can be
    // absolutely positioned. Two sizing modes (must match applyScaleSize
    // in LivePreview):
    //   - scale >= 1: min-width/min-height = scale*100%, width/height auto
    //     (cover behaviour, image overflows slot in at least one axis)
    //   - scale  < 1: width = scale*100%, height auto (image shrinks below
    //     slot size, aspect preserved). Translate moves it from center.
    const sizeStyle =
      state.scale >= 1
        ? `min-width:${pct}%;min-height:${pct}%;width:auto;height:auto;`
        : `min-width:0;min-height:0;width:${pct}%;height:auto;`;
    return (
      `<span data-slot-wrapper="${label}" ` +
      `style="position:relative;display:block;width:100%;height:100%;overflow:hidden;">` +
      `<img src="${state.dataUrl}" data-slot="${label}" ` +
      `data-pan-x="${state.panX}" data-pan-y="${state.panY}" data-scale="${state.scale}" ` +
      `style="position:absolute;left:50%;top:50%;` +
      `${sizeStyle}max-width:none;max-height:none;` +
      `transform:translate(calc(-50% + ${state.panX}px), calc(-50% + ${state.panY}px));` +
      `transform-origin:center;" />` +
      `</span>`
    );
  });
}
