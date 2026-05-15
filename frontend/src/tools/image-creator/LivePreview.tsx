import { useRef, useEffect, useState, useLayoutEffect } from "react";
import type { ImageState } from "./htmlBuilder";

interface LivePreviewProps {
  html: string;
  activeSlot: string | null;
  onImageStateChange: (label: string, state: Partial<ImageState>) => void;
}

const PADDING = 20;

export function LivePreview({ html, activeSlot, onImageStateChange }: LivePreviewProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);
  const [scale, setScale] = useState(1);

  // After iframe content loads, measure the rendered template at its native
  // pixel size. We trust the first element child of <body> to be the template
  // root (e.g. <div class="card">). Templates are rendered inside an iframe
  // for full CSS isolation — global selectors like `* { margin: 0 }` won't
  // bleed into the host app.
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
  }

  // Auto-fit the template to the available preview area. Recompute on every
  // wrapper resize and every time the template's natural size changes.
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

  // Pointer/wheel handlers attached inside the iframe document. Coordinates
  // from these events are already in template-native space (because the
  // iframe's own viewport is the template's coordinate system), so no scale
  // correction is needed.
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !activeSlot || !naturalSize) return;
    const doc = iframe.contentDocument;
    if (!doc) return;
    const el = doc.querySelector<HTMLImageElement>(`[data-slot="${activeSlot}"]`);
    if (!el) return;

    function onPointerDown(e: PointerEvent) {
      e.preventDefault();
      const style = el!.style;
      const posX = parseFloat(style.objectPosition?.split(" ")[0] ?? "50") || 50;
      const posY = parseFloat(style.objectPosition?.split(" ")[1] ?? "50") || 50;
      dragRef.current = { startX: e.clientX, startY: e.clientY, startPosX: posX, startPosY: posY };
      el!.setPointerCapture(e.pointerId);
    }
    function onPointerMove(e: PointerEvent) {
      if (!dragRef.current || !el) return;
      const dx = ((e.clientX - dragRef.current.startX) / el.offsetWidth) * -100;
      const dy = ((e.clientY - dragRef.current.startY) / el.offsetHeight) * -100;
      const newX = Math.max(0, Math.min(100, dragRef.current.startPosX + dx));
      const newY = Math.max(0, Math.min(100, dragRef.current.startPosY + dy));
      el.style.objectPosition = `${newX}% ${newY}%`;
    }
    function onPointerUp(e: PointerEvent) {
      if (!dragRef.current || !el) return;
      const dx = ((e.clientX - dragRef.current.startX) / el.offsetWidth) * -100;
      const dy = ((e.clientY - dragRef.current.startY) / el.offsetHeight) * -100;
      const newX = Math.max(0, Math.min(100, dragRef.current.startPosX + dx));
      const newY = Math.max(0, Math.min(100, dragRef.current.startPosY + dy));
      dragRef.current = null;
      onImageStateChange(activeSlot!, { posX: newX, posY: newY });
    }
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const currentScale = parseFloat(el!.style.transform?.match(/scale\(([^)]+)\)/)?.[1] ?? "1") || 1;
      const delta = e.deltaY < 0 ? 0.1 : -0.1;
      const newScale = Math.max(1, Math.min(3, currentScale + delta));
      el!.style.transform = `scale(${newScale})`;
      onImageStateChange(activeSlot!, { scale: newScale });
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
