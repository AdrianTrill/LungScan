import type { Label } from "./types";

/** The model's classes, in the order of its outputs. */
export const LABELS: Label[] = [
  "adenocarcinoma",
  "large_cell_carcinoma",
  "normal",
  "squamous_cell_carcinoma",
];

export const NORMAL = 2;
export const CANCER = [0, 1, 3] as const;

export const LABEL_NAMES: Record<Label, string> = {
  adenocarcinoma: "Adenocarcinoma",
  large_cell_carcinoma: "Large cell carcinoma",
  normal: "Normal",
  squamous_cell_carcinoma: "Squamous cell carcinoma",
};

export const LABEL_SHORT: Record<Label, string> = {
  adenocarcinoma: "Adeno",
  large_cell_carcinoma: "Large cell",
  normal: "Normal",
  squamous_cell_carcinoma: "Squamous",
};
