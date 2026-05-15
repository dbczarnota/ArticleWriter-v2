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
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);
  const [scale, setScale] = useState(1);
  const scaleRef = useRef(1);
  scaleRef.current = scale;

  // Auto-fit the rendered template to the preview area. Templates are
  // authored at their natural pixel size (e.g. 1280x720) but the preview
  // pane is typically narrower, so without scaling the user only sees a
  // corner. Recompute on every html change and on container resize.
  useLayoutEffect(() => {
    const wrapper = wrapperRef.current;
    const container = containerRef.current;
    if (!wrapper || !container) return;

    function recompute() {
      if (!wrapper || !container) return;
      const child = container.firstElementChild as HTMLElement | null;
      if (!child) return;
      const naturalW = child.offsetWidth;
      const naturalH = child.offsetHeight;
      if (naturalW === 0 || naturalH === 0) return;
      const availW = wrapper.clientWidth - PADDING * 2;
      const availH = wrapper.clientHeight - PADDING * 2;
      // Don't upscale beyond 1 — tiny templates should render at native size,
      // only oversized ones get shrunk.
      const next = Math.min(availW / naturalW, availH / naturalH, 1);
      setScale(next > 0 ? next : 1);
    }

    recompute();
    const ro = new ResizeObserver(recompute);
    ro.observe(wrapper);
    return () => ro.disconnect();
  }, [html]);

  useEffect(() => {
    if (!containerRef.current || !activeSlot) return;
    const el = containerRef.current.querySelector<HTMLImageElement>(`[data-slot="${activeSlot}"]`);
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
      // Screen-space deltas need to be expanded by 1/scale to map back into
      // template coordinates before we divide by offsetWidth.
      const dxTemplate = (e.clientX - dragRef.current.startX) / scaleRef.current;
      const dyTemplate = (e.clientY - dragRef.current.startY) / scaleRef.current;
      const dx = (dxTemplate / el.offsetWidth) * -100;
      const dy = (dyTemplate / el.offsetHeight) * -100;
      const newX = Math.max(0, Math.min(100, dragRef.current.startPosX + dx));
      const newY = Math.max(0, Math.min(100, dragRef.current.startPosY + dy));
      el.style.objectPosition = `${newX}% ${newY}%`;
    }

    function onPointerUp(e: PointerEvent) {
      if (!dragRef.current || !el) return;
      const dxTemplate = (e.clientX - dragRef.current.startX) / scaleRef.current;
      const dyTemplate = (e.clientY - dragRef.current.startY) / scaleRef.current;
      const dx = (dxTemplate / el.offsetWidth) * -100;
      const dy = (dyTemplate / el.offsetHeight) * -100;
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
  }, [html, activeSlot, onImageStateChange]);

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
      <div
        ref={containerRef}
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: html }}
        style={{
          transform: `scale(${scale})`,
          transformOrigin: "center center",
          boxShadow: "0 4px 16px rgba(0,0,0,.08)",
          flexShrink: 0,
        }}
      />
    </div>
  );
}
