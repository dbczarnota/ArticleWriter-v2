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
  onImageStateChange: (label: string, state: Partial<ImageState>) => void;
}

const PADDING = 20;

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

export function LivePreview({ html, imageStates, activeSlot, onImageStateChange }: LivePreviewProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; startPanX: number; startPanY: number } | null>(null);
  const wheelCommitRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);
  const [scale, setScale] = useState(1);

  // Keep a ref to the latest imageStates so wheel/drag handlers and the
  // iframe-load handler can read fresh values without re-binding.
  const imageStatesRef = useRef(imageStates);
  imageStatesRef.current = imageStates;

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

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !activeSlot || !naturalSize) return;
    const doc = iframe.contentDocument;
    if (!doc) return;
    const el = doc.querySelector<HTMLImageElement>(`[data-slot="${activeSlot}"]`);
    if (!el) return;

    function onPointerDown(e: PointerEvent) {
      e.preventDefault();
      const startPanX = parseFloat(el!.dataset.panX ?? "0") || 0;
      const startPanY = parseFloat(el!.dataset.panY ?? "0") || 0;
      dragRef.current = { startX: e.clientX, startY: e.clientY, startPanX, startPanY };
      el!.setPointerCapture(e.pointerId);
    }
    function onPointerMove(e: PointerEvent) {
      if (!dragRef.current || !el) return;
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      const [px, py] = clampPan(
        dragRef.current.startPanX + dx,
        dragRef.current.startPanY + dy,
        el,
      );
      applyTransform(el, px, py);
    }
    function onPointerUp() {
      if (!dragRef.current || !el) return;
      const finalPanX = parseFloat(el.dataset.panX ?? "0") || 0;
      const finalPanY = parseFloat(el.dataset.panY ?? "0") || 0;
      dragRef.current = null;
      onImageStateChange(activeSlot!, { panX: finalPanX, panY: finalPanY });
    }
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const currentScale = parseFloat(el!.dataset.scale ?? "1") || 1;
      const delta = e.deltaY < 0 ? 0.1 : -0.1;
      const newScale = Math.max(1, Math.min(3, +(currentScale + delta).toFixed(2)));
      el!.style.minWidth = `${newScale * 100}%`;
      el!.style.minHeight = `${newScale * 100}%`;
      el!.dataset.scale = String(newScale);
      // Re-clamp pan against new image size so the picture never leaves the
      // slot when zooming back out.
      const panX = parseFloat(el!.dataset.panX ?? "0") || 0;
      const panY = parseFloat(el!.dataset.panY ?? "0") || 0;
      // offsetWidth/Height update synchronously after style write in Chrome.
      const [px, py] = clampPan(panX, panY, el!);
      applyTransform(el!, px, py);
      // Debounce the React state push — every wheel tick used to trigger a
      // state update which (even with stable srcDoc) caused a re-render
      // cascade. Now we commit only after the user stops scrolling.
      if (wheelCommitRef.current) clearTimeout(wheelCommitRef.current);
      wheelCommitRef.current = setTimeout(() => {
        const finalScale = parseFloat(el!.dataset.scale ?? "1") || 1;
        const finalPanX = parseFloat(el!.dataset.panX ?? "0") || 0;
        const finalPanY = parseFloat(el!.dataset.panY ?? "0") || 0;
        onImageStateChange(activeSlot!, { scale: finalScale, panX: finalPanX, panY: finalPanY });
      }, 200);
    }

    el.style.cursor = "grab";
    el.addEventListener("pointerdown", onPointerDown);
    el.addEventListener("pointermove", onPointerMove);
    el.addEventListener("pointerup", onPointerUp);
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      el.style.cursor = "";
      el.removeEventListener("pointerdown", onPointerDown);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerup", onPointerUp);
      el.removeEventListener("wheel", onWheel);
      if (wheelCommitRef.current) {
        clearTimeout(wheelCommitRef.current);
        wheelCommitRef.current = null;
      }
    };
  }, [html, activeSlot, naturalSize, onImageStateChange]);

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
