import { useRef, useEffect } from "react";
import type { ImageState } from "./htmlBuilder";

interface LivePreviewProps {
  html: string;
  activeSlot: string | null;
  onImageStateChange: (label: string, state: Partial<ImageState>) => void;
}

export function LivePreview({ html, activeSlot, onImageStateChange }: LivePreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);

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
  }, [html, activeSlot, onImageStateChange]);

  return (
    <div style={{ flex: 1, overflow: "auto", background: "#1a1a2e", position: "relative" }}>
      {activeSlot && (
        <div style={{ position: "absolute", top: 6, left: 0, right: 0, textAlign: "center", zIndex: 10, pointerEvents: "none" }}>
          <span style={{ background: "rgba(79,70,229,.8)", color: "white", fontSize: 10, padding: "2px 8px", borderRadius: 10, fontWeight: 600 }}>
            ↔ Przeciągnij · Scroll = zoom
          </span>
        </div>
      )}
      <div
        ref={containerRef}
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: html }}
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}
