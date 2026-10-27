import { useEffect, useRef } from "react";
import { usePreferences } from "@/app/preferencesContext";
import { drawStaticField } from "./field";

/**
 * Background "pulse field" (DESIGN.md §7): a faint two-tone field and one ECG-like trace,
 * drawn on a canvas behind all content. Phase B-F1 renders a single static frame; the
 * activity-driven animation is added in B-F4.
 */
export function PulseField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { resolvedTheme } = usePreferences();

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext?.("2d");
    if (!canvas || !ctx) return;
    const render = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const { innerWidth: w, innerHeight: h } = window;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawStaticField(ctx, w, h, resolvedTheme);
    };
    render();
    window.addEventListener("resize", render);
    return () => window.removeEventListener("resize", render);
  }, [resolvedTheme]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      data-testid="pulse-field"
      className="pointer-events-none fixed inset-0 -z-0 size-full"
    />
  );
}
