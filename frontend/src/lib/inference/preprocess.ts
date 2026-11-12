/**
 * The network's input, prepared as backend/app/services/model.py prepares it: resize to
 * 250x250, then 256x256, crop the central 224x224, and normalize each channel with the
 * ImageNet statistics, in float32 as NumPy computes it.
 */
import { resizeBilinear } from "./resample";

export const STAGED_SIZE = 250;
export const RESIZED_SIZE = 256;
export const CROP_SIZE = 224;
export const CROP_OFFSET = (RESIZED_SIZE - CROP_SIZE) / 2;

const f32 = Math.fround;
const MEAN = [0.485, 0.456, 0.406].map(f32);
const STD = [0.229, 0.224, 0.225].map(f32);
const SCALE = f32(255);

export interface RgbImage {
  rgb: Uint8Array;
  width: number;
  height: number;
}

/** Decode an image file to 8-bit RGB, ignoring alpha and color profiles, as Pillow does. */
export async function decodeRgb(blob: Blob): Promise<RgbImage> {
  const bitmap = await createImageBitmap(blob, {
    colorSpaceConversion: "none",
    premultiplyAlpha: "none",
  });
  const { width, height } = bitmap;
  const canvas =
    typeof OffscreenCanvas !== "undefined"
      ? new OffscreenCanvas(width, height)
      : Object.assign(document.createElement("canvas"), { width, height });
  const ctx = canvas.getContext("2d", { willReadFrequently: true }) as
    CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D;
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  const rgba = ctx.getImageData(0, 0, width, height).data;
  const rgb = new Uint8Array(width * height * 3);
  for (let i = 0, j = 0; i < rgba.length; i += 4, j += 3) {
    rgb[j] = rgba[i];
    rgb[j + 1] = rgba[i + 1];
    rgb[j + 2] = rgba[i + 2];
  }
  return { rgb, width, height };
}

/** The 256x256 image the crop is taken from. */
export function resized(image: RgbImage): Uint8Array {
  const staged = resizeBilinear(image.rgb, image.width, image.height, STAGED_SIZE, STAGED_SIZE);
  return resizeBilinear(staged, STAGED_SIZE, STAGED_SIZE, RESIZED_SIZE, RESIZED_SIZE);
}

/** The network's input: 1x3x224x224, channels first. */
export function toInput(image: RgbImage): Float32Array {
  const pixels = resized(image);
  const plane = CROP_SIZE * CROP_SIZE;
  const out = new Float32Array(3 * plane);
  for (let y = 0; y < CROP_SIZE; y++) {
    for (let x = 0; x < CROP_SIZE; x++) {
      const p = ((y + CROP_OFFSET) * RESIZED_SIZE + x + CROP_OFFSET) * 3;
      for (let c = 0; c < 3; c++) {
        const scaled = f32(pixels[p + c] / SCALE);
        out[c * plane + y * CROP_SIZE + x] = f32(f32(scaled - MEAN[c]) / STD[c]);
      }
    }
  }
  return out;
}
