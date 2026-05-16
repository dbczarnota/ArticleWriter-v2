import { useRef, useEffect, useState, useLayoutEffect } from "react";
import type { ImageState } from "./htmlBuilder";

interface LivePreviewProps {
  html: string;
  /** Current pan/zoom for each slot, applied to the DOM after iframe load.
   * The iframe srcDoc itself ignores pan/zoom (always renders at defaults)
   * so srcDoc stays byte-identical across pan/zoom changes and the iframe
   * doesn't reload mid-interaction. */
  imageStates: Record<string, ImageState>;
  activeSlot: string | null;
  onActivateSlot: (label: string) => void;
  onImageStateChange: (label: string, state: Partial<ImageState>) => void;
}

const PADDING = 20;
const PAN_STEP = 30;
const ZOOM_STEP = 0.15;

function applyTransform(el: HTMLImageElement, panX: number, panY: number) {
  el.style.transform = `translate(calc(-50% + ${panX}px), calc(-50% + ${panY}px))`;
  el.dataset.panX = String(panX);
  el.dataset.panY = String(panY);
}

function clampPan(panX: number, panY: number, el: HTMLImageElement): [number, number] {
  const slot = el.parentElement;
  if (!slot) return [panX, panY];
  const maxX = Math.max(0, (el.offsetWidth - slot.clientWidth) / 2);
  const maxY = Math.max(0, (el.offsetHeight - slot.clientHeight) / 2);
  return [
    Math.max(-maxX, Math.min(maxX, panX)),
    Math.max(-maxY, Math.min(maxY, panY)),
  ];
}

function nudgeZoom(
  el: HTMLImageElement,
  slot: string,
  delta: number,
  commit: (label: string, state: Partial<ImageState>) => void,
) {
  const cur = parseFloat(el.dataset.scale ?? "1") || 1;
  const next = Math.max(1, Math.min(3, +(cur + delta).toFixed(2)));
  el.style.minWidth = `${next * 100}%`;
  el.style.minHeight = `${next * 100}%`;
  el.dataset.scale = String(next);
  const panX = parseFloat(el.dataset.panX ?? "0") || 0;
  const panY = parseFloat(el.dataset.panY ?? "0") || 0;
  const [px, py] = clampPan(panX, panY, el);
  applyTransform(el, px, py);
  commit(slot, { scale: next, panX: px, panY: py });
}

function nudgePan(
  el: HTMLImageElement,
  slot: string,
  dx: number,
  dy: number,
  commit: (label: string, state: Partial<ImageState>) => void,
) {
  const panX = parseFloat(el.dataset.panX ?? "0") || 0;
  const panY = parseFloat(el.dataset.panY ?? "0") || 0;
  const [px, py] = clampPan(panX + dx, panY + dy, el);
  applyTransform(el, px, py);
  commit(slot, { panX: px, panY: py });
}

export function LivePreview({ html, imageStates, activeSlot, onActivateSlot, onImageStateChange }: LivePreviewProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);
  const [scale, setScale] = useState(1);

  // Refs so per-slot handlers read fresh values without re-binding the
  // whole effect on every render.
  const imageStatesRef = useRef(imageStates);
  imageStatesRef.current = imageStates;
  const activeSlotRef = useRef(activeSlot);
  activeSlotRef.current = activeSlot;
  const onActivateSlotRef = useRef(onActivateSlot);
  onActivateSlotRef.current = onActivateSlot;
  const onImageStateChangeRef = useRef(onImageStateChange);
  onImageStateChangeRef.current = onImageStateChange;

  function handleLoad() {
    const doc = iframeRef.current?.contentDocument;
    if (!doc || !doc.body) return;
    const card = doc.body.firstElementChild as HTMLElement | null;
    if (!card) return;
    const w = card.offsetWidth;
    const h = card.offsetHeight;
    if (w > 0 && h > 0) {
      setNaturalSize({ w, h });
    }
    // srcDoc renders images at defaults (panX=0, panY=0, scale=1) — apply the
    // current state to each <img data-slot=...> imperatively so persisted
    // pan/zoom is restored on reload (which only happens on text/image
    // structural changes, not on pan/zoom).
    const imgs = doc.querySelectorAll<HTMLImageElement>("[data-slot]");
    imgs.forEach((el) => {
      const slot = el.dataset.slot;
      if (!slot) return;
      const st = imageStatesRef.current[slot];
      if (!st) return;
      el.style.minWidth = `${st.scale * 100}%`;
      el.style.minHeight = `${st.scale * 100}%`;
      el.style.transform = `translate(calc(-50% + ${st.panX}px), calc(-50% + ${st.panY}px))`;
      el.dataset.panX = String(st.panX);
      el.dataset.panY = String(st.panY);
      el.dataset.scale = String(st.scale);
    });
  }

  useLayoutEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper || !naturalSize) return;
    function recompute() {
      const availW = wrapper!.clientWidth - PADDING * 2;
      const availH = wrapper!.clientHeight - PADDING * 2;
      const next = Math.min(availW / naturalSize!.w, availH / naturalSize!.h, 1);
      setScale(next > 0 ? next : 1);
    }
    recompute();
    const ro = new ResizeObserver(recompute);
    ro.observe(wrapper);
    return () => ro.disconnect();
  }, [naturalSize]);

  // Bind pan/zoom handlers AND inject on-screen controls per slot. Hover-
  // entering a slot makes it the active one (so the left column highlight
  // follows the mouse) — no need to click the slot list before zooming.
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !naturalSize) return;
    const doc = iframe.contentDocument;
    if (!doc) return;

    const slots = Array.from(doc.querySelectorAll<HTMLImageElement>("[data-slot]"));
    const cleanups: Array<() => void> = [];
    const commit: (label: string, st: Partial<ImageState>) => void = (label, st) =>
      onImageStateChangeRef.current(label, st);

    slots.forEach((el) => {
      const slot = el.dataset.slot;
      if (!slot) return;

      let drag: { startX: number; startY: number; startPanX: number; startPanY: number } | null = null;
      let wheelTimer: ReturnType<typeof setTimeout> | null = null;

      function onPointerEnter() {
        if (activeSlotRef.current !== slot) onActivateSlotRef.current(slot!);
      }
      function onPointerDown(e: PointerEvent) {
        e.preventDefault();
        const startPanX = parseFloat(el.dataset.panX ?? "0") || 0;
        const startPanY = parseFloat(el.dataset.panY ?? "0") || 0;
        drag = { startX: e.clientX, startY: e.clientY, startPanX, startPanY };
        el.setPointerCapture(e.pointerId);
      }
      function onPointerMove(e: PointerEvent) {
        if (!drag) return;
        const dx = e.clientX - drag.startX;
        const dy = e.clientY - drag.startY;
        const [px, py] = clampPan(drag.startPanX + dx, drag.startPanY + dy, el);
        applyTransform(el, px, py);
      }
      function onPointerUp() {
        if (!drag) return;
        drag = null;
        const finalPanX = parseFloat(el.dataset.panX ?? "0") || 0;
        const finalPanY = parseFloat(el.dataset.panY ?? "0") || 0;
        commit(slot!, { panX: finalPanX, panY: finalPanY });
      }
      function onWheel(e: WheelEvent) {
        e.preventDefault();
        const cur = parseFloat(el.dataset.scale ?? "1") || 1;
        const delta = e.deltaY < 0 ? 0.1 : -0.1;
        const next = Math.max(1, Math.min(3, +(cur + delta).toFixed(2)));
        el.style.minWidth = `${next * 100}%`;
        el.style.minHeight = `${next * 100}%`;
        el.dataset.scale = String(next);
        const panX = parseFloat(el.dataset.panX ?? "0") || 0;
        const panY = parseFloat(el.dataset.panY ?? "0") || 0;
        const [px, py] = clampPan(panX, panY, el);
        applyTransform(el, px, py);
        if (wheelTimer) clearTimeout(wheelTimer);
        wheelTimer = setTimeout(() => {
          commit(slot!, { scale: next, panX: px, panY: py });
        }, 200);
      }

      el.style.cursor = "grab";
      el.addEventListener("pointerenter", onPointerEnter);
      el.addEventListener("pointerdown", onPointerDown);
      el.addEventListener("pointermove", onPointerMove);
      el.addEventListener("pointerup", onPointerUp);
      el.addEventListener("wheel", onWheel, { passive: false });

      // Inject on-screen controls (−, +, ◀, ▲, ▼, ▶) into the slot's
      // parent, so they ride on top of the image inside the overflow:hidden
      // crop. Subtle by default, full opacity on hover. Accessibility
      // fallback for users without a working mouse wheel.
      const parent = el.parentElement;
      let removeBar = () => {};
      if (parent) {
        parent.querySelector(".aw-slot-controls")?.remove();
        const view = doc.defaultView;
        if (view && view.getComputedStyle(parent).position === "static") {
          parent.style.position = "relative";
        }

        const bar = doc.createElement("div");
        bar.className = "aw-slot-controls";
        bar.style.cssText =
          "position:absolute;bottom:8px;left:50%;transform:translateX(-50%);" +
          "display:flex;gap:1px;align-items:center;background:rgba(0,0,0,.55);" +
          "padding:3px;border-radius:6px;opacity:.3;transition:opacity .15s;" +
          "z-index:5;font-family:system-ui,sans-serif;backdrop-filter:blur(2px);";

        const mkBtn = (glyph: string, title: string, onClick: () => void) => {
          const b = doc.createElement("button");
          b.type = "button";
          b.title = title;
          b.textContent = glyph;
          b.style.cssText =
            "background:transparent;color:#fff;border:none;width:22px;height:22px;" +
            "padding:0;font:600 13px/1 inherit;cursor:pointer;border-radius:4px;" +
            "display:inline-flex;align-items:center;justify-content:center;user-select:none;";
          b.addEventListener("mouseenter", () => {
            b.style.background = "rgba(255,255,255,.22)";
          });
          b.addEventListener("mouseleave", () => {
            b.style.background = "transparent";
          });
          b.addEventListener("pointerdown", (e) => e.stopPropagation());
          b.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            onClick();
          });
          return b;
        };

        bar.appendChild(mkBtn("−", "Pomniejsz", () => nudgeZoom(el, slot!, -ZOOM_STEP, commit)));
        bar.appendChild(mkBtn("+", "Powiększ", () => nudgeZoom(el, slot!, +ZOOM_STEP, commit)));
        const sep = doc.createElement("span");
        sep.style.cssText = "display:inline-block;width:6px;";
        bar.appendChild(sep);
        bar.appendChild(mkBtn("◀", "Przesuń w lewo", () => nudgePan(el, slot!, -PAN_STEP, 0, commit)));
        bar.appendChild(mkBtn("▲", "Przesuń w górę", () => nudgePan(el, slot!, 0, -PAN_STEP, commit)));
        bar.appendChild(mkBtn("▼", "Przesuń w dół", () => nudgePan(el, slot!, 0, +PAN_STEP, commit)));
        bar.appendChild(mkBtn("▶", "Przesuń w prawo", () => nudgePan(el, slot!, +PAN_STEP, 0, commit)));

        bar.addEventListener("pointerenter", () => {
          bar.style.opacity = "1";
        });
        bar.addEventListener("pointerleave", () => {
          bar.style.opacity = ".3";
        });
        // Don't let pointer interactions on the toolbar start an image drag
        bar.addEventListener("pointerdown", (e) => e.stopPropagation());

        parent.appendChild(bar);
        removeBar = () => bar.remove();
      }

      cleanups.push(() => {
        el.style.cursor = "";
        el.removeEventListener("pointerenter", onPointerEnter);
        el.removeEventListener("pointerdown", onPointerDown);
        el.removeEventListener("pointermove", onPointerMove);
        el.removeEventListener("pointerup", onPointerUp);
        el.removeEventListener("wheel", onWheel);
        if (wheelTimer) clearTimeout(wheelTimer);
        removeBar();
      });
    });

    return () => cleanups.forEach((fn) => fn());
  }, [html, naturalSize]);

  return (
    <div
      ref={wrapperRef}
      style={{
        flex: 1,
        overflow: "hidden",
        background: "var(--canvas-bg)",
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: PADDING,
        minHeight: 0,
      }}
    >
      {activeSlot && (
        <div style={{ position: "absolute", top: 8, left: 0, right: 0, textAlign: "center", zIndex: 10, pointerEvents: "none" }}>
          <span style={{ background: "var(--accent)", color: "white", fontSize: 11, padding: "3px 10px", borderRadius: 10, fontWeight: 600 }}>
            ↔ Przeciągnij · Scroll = zoom
          </span>
        </div>
      )}
      <iframe
        ref={iframeRef}
        srcDoc={html}
        onLoad={handleLoad}
        title="Image template preview"
        scrolling="no"
        width={naturalSize?.w ?? 1280}
        height={naturalSize?.h ?? 720}
        style={{
          border: "none",
          transform: `scale(${scale})`,
          transformOrigin: "center center",
          flexShrink: 0,
          boxShadow: "0 4px 16px rgba(0,0,0,.08)",
          background: "#000",
          visibility: naturalSize ? "visible" : "hidden",
        }}
      />
    </div>
  );
}
