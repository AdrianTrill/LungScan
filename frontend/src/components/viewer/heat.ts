/** Drawing the Grad-CAM heat map: upsampling the 7x7 grid and coloring it. */

// An inferno-like ramp. Alpha rises with the evidence, so faint evidence stays see-through.
const STOPS: [number, [number, number, number, number]][] = [
  [0.0, [0, 0, 4, 0]],
  [0.36, [101, 21, 110, 0]],
  [0.5, [159, 42, 99, 0.42]],
  [0.65, [212, 72, 66, 0.64]],
  [0.8, [245, 125, 21, 0.8]],
  [1.0, [252, 255, 164, 0.9]],
];

export function heatColor(value: number): [number, number, number, number] {
  const v = Math.min(1, Math.max(0, value));
  for (let i = 1; i < STOPS.length; i++) {
    const [x1, c1] = STOPS[i];
    if (v <= x1) {
      const [x0, c0] = STOPS[i - 1];
      const t = (v - x0) / (x1 - x0);
      return [0, 1, 2, 3].map((k) => c0[k] + (c1[k] - c0[k]) * t) as [
        number,
        number,
        number,
        number,
      ];
    }
  }
  return STOPS[STOPS.length - 1][1];
}

/** The CSS gradient of the visible part of the ramp, for the legend. */
export const HEAT_GRADIENT = `linear-gradient(90deg, ${STOPS.slice(2)
  .map(([x, [r, g, b]]) => `rgb(${r} ${g} ${b}) ${Math.round(((x - 0.5) / 0.5) * 100)}%`)
  .join(", ")})`;

/** Bilinear value of the grid at (u, v) in [0, 1], with cell centers at (i + 0.5) / size. */
export function sampleGrid(values: number[], size: number, u: number, v: number): number {
  const x = Math.min(size - 1, Math.max(0, u * size - 0.5));
  const y = Math.min(size - 1, Math.max(0, v * size - 0.5));
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const x1 = Math.min(size - 1, x0 + 1);
  const y1 = Math.min(size - 1, y0 + 1);
  const fx = x - x0;
  const fy = y - y0;
  const top = values[y0 * size + x0] * (1 - fx) + values[y0 * size + x1] * fx;
  const bottom = values[y1 * size + x0] * (1 - fx) + values[y1 * size + x1] * fx;
  return top * (1 - fy) + bottom * fy;
}

/** 0 at the edge of the map, rising to 1 a few percent inside, so the crop's border never shows. */
function feather(u: number, v: number, width = 0.05): number {
  const d = Math.min(u, v, 1 - u, 1 - v) / width;
  const t = Math.min(1, Math.max(0, d));
  return t * t * (3 - 2 * t);
}

/** Paint the heat map into a canvas of resolution x resolution pixels. */
export function paintHeat(
  canvas: HTMLCanvasElement,
  values: number[],
  size: number,
  resolution = 112
) {
  canvas.width = resolution;
  canvas.height = resolution;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const image = ctx.createImageData(resolution, resolution);
  for (let py = 0; py < resolution; py++) {
    for (let px = 0; px < resolution; px++) {
      const u = (px + 0.5) / resolution;
      const v = (py + 0.5) / resolution;
      const [r, g, b, a] = heatColor(sampleGrid(values, size, u, v));
      const o = (py * resolution + px) * 4;
      image.data[o] = r;
      image.data[o + 1] = g;
      image.data[o + 2] = b;
      image.data[o + 3] = Math.round(a * feather(u, v) * 255);
    }
  }
  ctx.putImageData(image, 0, 0);
}
