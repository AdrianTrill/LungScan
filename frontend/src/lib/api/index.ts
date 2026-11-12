/** The backend this build talks to: the FastAPI server, or the browser itself. */
import { RUNTIME } from "../config";
import { browserApi } from "./browser";
import { serverApi } from "./server";

export type { AnalyzeProgress, LungScanApi, ModelStatus } from "./types";

export const api = RUNTIME === "browser" ? browserApi : serverApi;
