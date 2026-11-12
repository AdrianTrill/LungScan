/**
 * Bilinear resampling exactly as Pillow 13 does it for 8-bit images (libImaging/Resample.c):
 * a triangle filter widened by the downscale factor, weights in fixed point with 22
 * fractional bits, rounding, and a horizontal pass stored as 8 bits before the vertical
 * one. The server resizes with Pillow, so both see the same pixels.
 */

const PRECISION_BITS = 22;
const ONE = 1 << PRECISION_BITS;
const HALF = 1 << (PRECISION_BITS - 1);

interface Coefficients {
  ksize: number;
  bounds: Int32Array;
  weights: Int32Array;
}

function coefficients(inSize: number, outSize: number): Coefficients {
  const scale = inSize / outSize;
  const filterscale = Math.max(scale, 1);
  const support = filterscale;
  const ksize = Math.ceil(support) * 2 + 1;
  const bounds = new Int32Array(outSize * 2);
  const weights = new Int32Array(outSize * ksize);
  const k = new Float64Array(ksize);
  for (let xx = 0; xx < outSize; xx++) {
    const center = (xx + 0.5) * scale;
    const ss = 1 / filterscale;
    const xmin = Math.max(0, Math.trunc(center - support + 0.5));
    const xmax = Math.min(inSize, Math.trunc(center + support + 0.5)) - xmin;
    let total = 0;
    for (let x = 0; x < xmax; x++) {
      const t = Math.abs((x + xmin - center + 0.5) * ss);
      k[x] = t < 1 ? 1 - t : 0;
      total += k[x];
    }
    for (let x = 0; x < xmax; x++) {
      const w = total !== 0 ? k[x] / total : k[x];
      weights[xx * ksize + x] = Math.trunc(0.5 + w * ONE);
    }
    bounds[xx * 2] = xmin;
    bounds[xx * 2 + 1] = xmax;
  }
  return { ksize, bounds, weights };
}

function clip8(sum: number): number {
  const v = sum >> PRECISION_BITS;
  return v < 0 ? 0 : v > 255 ? 255 : v;
}

function horizontal(data: Uint8Array, width: number, height: number, outWidth: number): Uint8Array {
  const { ksize, bounds, weights } = coefficients(width, outWidth);
  const out = new Uint8Array(outWidth * height * 3);
  for (let y = 0; y < height; y++) {
    const row = y * width * 3;
    for (let xx = 0; xx < outWidth; xx++) {
      const xmin = bounds[xx * 2];
      const xmax = bounds[xx * 2 + 1];
      const k = xx * ksize;
      let s0 = HALF;
      let s1 = HALF;
      let s2 = HALF;
      for (let x = 0; x < xmax; x++) {
        const p = row + (x + xmin) * 3;
        const weight = weights[k + x];
        s0 += data[p] * weight;
        s1 += data[p + 1] * weight;
        s2 += data[p + 2] * weight;
      }
      const o = (y * outWidth + xx) * 3;
      out[o] = clip8(s0);
      out[o + 1] = clip8(s1);
      out[o + 2] = clip8(s2);
    }
  }
  return out;
}

function vertical(data: Uint8Array, width: number, height: number, outHeight: number): Uint8Array {
  const { ksize, bounds, weights } = coefficients(height, outHeight);
  const out = new Uint8Array(width * outHeight * 3);
  for (let yy = 0; yy < outHeight; yy++) {
    const ymin = bounds[yy * 2];
    const ymax = bounds[yy * 2 + 1];
    const k = yy * ksize;
    for (let x = 0; x < width; x++) {
      let s0 = HALF;
      let s1 = HALF;
      let s2 = HALF;
      for (let y = 0; y < ymax; y++) {
        const p = ((y + ymin) * width + x) * 3;
        const weight = weights[k + y];
        s0 += data[p] * weight;
        s1 += data[p + 1] * weight;
        s2 += data[p + 2] * weight;
      }
      const o = (yy * width + x) * 3;
      out[o] = clip8(s0);
      out[o + 1] = clip8(s1);
      out[o + 2] = clip8(s2);
    }
  }
  return out;
}

/**
 * Resize interleaved RGB pixels, as Image.resize((outWidth, outHeight), BILINEAR) does in
 * Pillow 13: horizontal pass first, unless the height shrinks by more than twice as many
 * pixels as the width does.
 */
export function resizeBilinear(
  src: Uint8Array,
  width: number,
  height: number,
  outWidth: number,
  outHeight: number
): Uint8Array {
  const needHorizontal = outWidth !== width;
  const needVertical = outHeight !== height;
  const horizontalFirst = !(height - outHeight > 0 && height - outHeight > (width - outWidth) * 2);
  let data = src;
  if (horizontalFirst) {
    if (needHorizontal) data = horizontal(data, width, height, outWidth);
    if (needVertical) data = vertical(data, outWidth, height, outHeight);
  } else {
    if (needVertical) data = vertical(data, width, height, outHeight);
    if (needHorizontal) data = horizontal(data, width, outHeight, outWidth);
  }
  return data === src ? src.slice() : data;
}
