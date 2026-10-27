/** Drawing routines for the background pulse field (DESIGN.md §7). */

const BASE = {
  light: { field: [14, 92, 112], field2: [34, 96, 58], trace: [14, 92, 112] },
  dark: { field: [93, 180, 200], field2: [143, 208, 162], trace: [124, 196, 213] },
} as const;

export function drawStaticField(ctx: CanvasRenderingContext2D, width: number, height: number, theme: "light" | "dark") {
  const c = BASE[theme];
  ctx.clearRect(0, 0, width, height);

  const glowA = ctx.createRadialGradient(width * 0.15, height * 0.1, 0, width * 0.15, height * 0.1, width * 0.6);
  glowA.addColorStop(0, `rgba(${c.field.join(",")},0.07)`);
  glowA.addColorStop(1, `rgba(${c.field.join(",")},0)`);
  ctx.fillStyle = glowA;
  ctx.fillRect(0, 0, width, height);

  const glowB = ctx.createRadialGradient(width * 0.9, height * 0.95, 0, width * 0.9, height * 0.95, width * 0.55);
  glowB.addColorStop(0, `rgba(${c.field2.join(",")},0.05)`);
  glowB.addColorStop(1, `rgba(${c.field2.join(",")},0)`);
  ctx.fillStyle = glowB;
  ctx.fillRect(0, 0, width, height);

  // One faint ECG-like trace near the bottom third.
  const y0 = height * 0.78;
  ctx.strokeStyle = `rgba(${c.trace.join(",")},0.08)`;
  ctx.lineWidth = 1.25;
  ctx.beginPath();
  const period = 320;
  for (let x = 0; x <= width; x += 2) {
    const phase = (x % period) / period;
    let y = 0;
    if (phase > 0.42 && phase < 0.46) y = -6 * Math.sin(((phase - 0.42) / 0.04) * Math.PI);
    else if (phase > 0.5 && phase < 0.52) y = 14 * ((phase - 0.5) / 0.02);
    else if (phase >= 0.52 && phase < 0.55) y = 14 - 52 * ((phase - 0.52) / 0.03);
    else if (phase >= 0.55 && phase < 0.58) y = -38 + 44 * ((phase - 0.55) / 0.03);
    else if (phase > 0.66 && phase < 0.74) y = -8 * Math.sin(((phase - 0.66) / 0.08) * Math.PI);
    if (x === 0) ctx.moveTo(x, y0 + y);
    else ctx.lineTo(x, y0 + y);
  }
  ctx.stroke();
}
