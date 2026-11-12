"use client";

/**
 * The slice viewer: zoom and pan, window and level, inversion, the Grad-CAM heat map, and
 * the regions, with corner annotations as in a PACS viewer. The image and its overlays
 * share one CSS transform; window and level are an exact linear transfer (an SVG filter),
 * so the pixels underneath are never resampled for display adjustments.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useShortcuts } from "@/lib/hooks";
import type { AnalyzeResult } from "@/lib/types";
import Icon, { type IconName } from "../ui/Icon";
import { HEAT_GRADIENT, paintHeat, sampleGrid } from "./heat";

export interface ViewerFocus {
  regionId: string;
  nonce: number;
}

interface ViewerProps {
  src: string | null;
  result: AnalyzeResult | null;
  topLeft?: string[];
  topRight?: string[];
  scanning?: boolean;
  highlight?: string | null;
  focus?: ViewerFocus | null;
}

interface View {
  scale: number;
  tx: number;
  ty: number;
  fitted: boolean;
}

const DEFAULT_WINDOW = { width: 255, level: 127.5 };
const MIN_SCALE = 0.05;
const MAX_SCALE = 24;

function ToolButton({
  icon,
  label,
  shortcut,
  active,
  onClick,
  children,
}: {
  icon?: IconName;
  label: string;
  shortcut?: string;
  active?: boolean;
  onClick: () => void;
  children?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={shortcut ? `${label} (${shortcut})` : label}
      aria-label={label}
      aria-pressed={active}
      className={`flex h-8 min-w-8 items-center justify-center gap-1 rounded-md px-1.5 text-[12px] transition ${
        active ? "bg-accent/20 text-accent" : "text-slate-300 hover:bg-white/10 hover:text-white"
      }`}
    >
      {icon && <Icon name={icon} className="h-4 w-4" />}
      {children}
    </button>
  );
}

export default function Viewer({
  src,
  result,
  topLeft = [],
  topRight = [],
  scanning = false,
  highlight = null,
  focus = null,
}: ViewerProps) {
  const filterId = `window-${useId().replace(/:/g, "")}`;
  const container = useRef<HTMLDivElement>(null);
  const heatCanvas = useRef<HTMLCanvasElement>(null);
  const pixels = useRef<CanvasRenderingContext2D | null>(null);
  const drag = useRef<{
    x: number;
    y: number;
    view: View;
    win: typeof DEFAULT_WINDOW;
    mode: "pan" | "window";
  } | null>(null);

  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const [failed, setFailed] = useState(false);
  const [view, setView] = useState<View>({ scale: 1, tx: 0, ty: 0, fitted: true });
  const [tool, setTool] = useState<"pan" | "window">("pan");
  const [win, setWin] = useState(DEFAULT_WINDOW);
  const [invert, setInvert] = useState(false);
  const [showHeat, setShowHeat] = useState(true);
  const [opacity, setOpacity] = useState(0.75);
  const [showRegions, setShowRegions] = useState(true);
  const [cursor, setCursor] = useState<{
    x: number;
    y: number;
    value: number;
    heat: number | null;
  } | null>(null);

  const fitView = useCallback((): View | null => {
    const box = container.current?.getBoundingClientRect();
    if (!box || !size) return null;
    const scale = Math.min(box.width / size.width, box.height / size.height) * 0.92;
    return {
      scale,
      tx: (box.width - size.width * scale) / 2,
      ty: (box.height - size.height * scale) / 2,
      fitted: true,
    };
  }, [size]);

  const fit = useCallback(() => {
    const next = fitView();
    if (next) setView(next);
  }, [fitView]);

  // Refit when the image or the viewer's size changes, unless the reader has moved it.
  useEffect(() => {
    fit();
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setView((v) => (v.fitted ? (fitView() ?? v) : v)));
    observer.observe(element);
    return () => observer.disconnect();
  }, [fit, fitView]);

  useEffect(() => {
    setFailed(false);
    setSize(null);
    pixels.current = null;
  }, [src]);

  useEffect(() => {
    if (heatCanvas.current && result)
      paintHeat(heatCanvas.current, result.heatmap.values, result.heatmap.size);
  }, [result, src, failed]);

  const zoomAt = useCallback((factor: number, px?: number, py?: number) => {
    setView((v) => {
      const box = container.current?.getBoundingClientRect();
      const cx = px ?? (box ? box.width / 2 : 0);
      const cy = py ?? (box ? box.height / 2 : 0);
      const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor));
      const k = scale / v.scale;
      return { scale, tx: cx - (cx - v.tx) * k, ty: cy - (cy - v.ty) * k, fitted: false };
    });
  }, []);

  const actualSize = useCallback(() => {
    const box = container.current?.getBoundingClientRect();
    if (!box || !size) return;
    setView({
      scale: 1,
      tx: (box.width - size.width) / 2,
      ty: (box.height - size.height) / 2,
      fitted: false,
    });
  }, [size]);

  const reset = useCallback(() => {
    setWin(DEFAULT_WINDOW);
    setInvert(false);
    fit();
  }, [fit]);

  // Center a region and zoom so that it fills about a third of the viewer.
  const latest = useRef({ result, size });
  latest.current = { result, size };
  useEffect(() => {
    const { result, size } = latest.current;
    if (!focus || !result || !size) return;
    const region = result.regions.find((r) => r.id === focus.regionId);
    const box = container.current?.getBoundingClientRect();
    if (!region || !box) return;
    const scale = Math.min(
      MAX_SCALE,
      Math.max(MIN_SCALE, Math.min(box.width, box.height) / (region.radius * 6))
    );
    setView({
      scale,
      tx: box.width / 2 - region.x * scale,
      ty: box.height / 2 - region.y * scale,
      fitted: false,
    });
  }, [focus]);

  useShortcuts({
    h: () => setShowHeat((v) => !v),
    r: () => setShowRegions((v) => !v),
    i: () => setInvert((v) => !v),
    p: () => setTool("pan"),
    w: () => setTool("window"),
    "+": () => zoomAt(1.25),
    "=": () => zoomAt(1.25),
    "-": () => zoomAt(0.8),
    f: fit,
    "1": actualSize,
    "0": reset,
  });

  // Wheel zoom around the cursor. React's onWheel is passive, so attach it directly.
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const box = element.getBoundingClientRect();
      zoomAt(Math.exp(-event.deltaY * 0.0015), event.clientX - box.left, event.clientY - box.top);
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  const onLoad = (event: React.SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setSize({ width: image.naturalWidth, height: image.naturalHeight });
    try {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      ctx?.drawImage(image, 0, 0);
      ctx?.getImageData(0, 0, 1, 1);
      pixels.current = ctx;
    } catch {
      pixels.current = null;
    }
  };

  const toImage = (clientX: number, clientY: number) => {
    const box = container.current!.getBoundingClientRect();
    return {
      x: (clientX - box.left - view.tx) / view.scale,
      y: (clientY - box.top - view.ty) / view.scale,
    };
  };

  const onPointerDown = (event: React.PointerEvent) => {
    if (event.button !== 0 && event.button !== 2) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    // The right button always adjusts the window, as in most viewers.
    const mode = event.button === 2 || tool === "window" ? "window" : "pan";
    drag.current = { x: event.clientX, y: event.clientY, view, win, mode };
  };

  const onPointerMove = (event: React.PointerEvent) => {
    const start = drag.current;
    if (start) {
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      if (start.mode === "window") {
        setWin({
          width: Math.min(510, Math.max(2, start.win.width + dx)),
          level: Math.min(255, Math.max(0, start.win.level - dy * 0.75)),
        });
      } else {
        setView({ ...start.view, tx: start.view.tx + dx, ty: start.view.ty + dy, fitted: false });
      }
    }
    if (!size) return;
    const { x, y } = toImage(event.clientX, event.clientY);
    if (x < 0 || y < 0 || x >= size.width || y >= size.height) {
      setCursor(null);
      return;
    }
    const px = Math.floor(x);
    const py = Math.floor(y);
    let value = NaN;
    if (pixels.current) {
      const [r, g, b] = pixels.current.getImageData(px, py, 1, 1).data;
      value = Math.round((r + g + b) / 3);
    }
    let heat: number | null = null;
    if (result) {
      const { box } = result.heatmap;
      const u = (x - box.x) / box.width;
      const v = (y - box.y) / box.height;
      if (u >= 0 && u <= 1 && v >= 0 && v <= 1)
        heat = sampleGrid(result.heatmap.values, result.heatmap.size, u, v);
    }
    setCursor({ x: px, y: py, value, heat });
  };

  const onPointerUp = () => {
    drag.current = null;
  };

  // Window and level as a linear transfer on each channel, out = slope * in + intercept.
  const transfer = useMemo(() => {
    const slope = 255 / win.width;
    const intercept = 0.5 - win.level / win.width;
    return invert ? { slope: -slope, intercept: 1 - intercept } : { slope, intercept };
  }, [win, invert]);

  const windowChanged = win.width !== DEFAULT_WINDOW.width || win.level !== DEFAULT_WINDOW.level;
  const heatBox = result?.heatmap.box;

  return (
    <div className="relative flex h-full min-h-[360px] flex-col overflow-hidden rounded-xl border border-line bg-viewer text-slate-200">
      <svg width="0" height="0" className="absolute" aria-hidden="true">
        <filter id={filterId} colorInterpolationFilters="sRGB">
          <feComponentTransfer>
            <feFuncR type="linear" slope={transfer.slope} intercept={transfer.intercept} />
            <feFuncG type="linear" slope={transfer.slope} intercept={transfer.intercept} />
            <feFuncB type="linear" slope={transfer.slope} intercept={transfer.intercept} />
          </feComponentTransfer>
        </filter>
      </svg>

      <div className="no-print z-20 flex flex-wrap items-center gap-0.5 border-b border-white/[0.07] bg-black/40 px-2 py-1 backdrop-blur">
        <ToolButton
          icon="pan"
          label="Drag pans"
          shortcut="P"
          active={tool === "pan"}
          onClick={() => setTool("pan")}
        />
        <ToolButton
          icon="window"
          label="Drag sets window and level"
          shortcut="W"
          active={tool === "window"}
          onClick={() => setTool("window")}
        />
        <span className="mx-1 h-5 w-px bg-white/10" />
        <ToolButton icon="zoomOut" label="Zoom out" shortcut="-" onClick={() => zoomAt(0.8)} />
        <span className="tabular w-12 text-center font-mono text-11 text-slate-400">
          {Math.round(view.scale * 100)}%
        </span>
        <ToolButton icon="zoomIn" label="Zoom in" shortcut="+" onClick={() => zoomAt(1.25)} />
        <ToolButton icon="fit" label="Fit to the viewer" shortcut="F" onClick={fit} />
        <ToolButton label="Actual size" shortcut="1" onClick={actualSize}>
          <span className="font-mono text-11">1:1</span>
        </ToolButton>
        <span className="mx-1 h-5 w-px bg-white/10" />
        <ToolButton
          icon="invert"
          label="Invert"
          shortcut="I"
          active={invert}
          onClick={() => setInvert((v) => !v)}
        />
        <span className="mx-1 h-5 w-px bg-white/10" />
        <ToolButton
          icon="heat"
          label="Grad-CAM heat map"
          shortcut="H"
          active={showHeat && !!result}
          onClick={() => setShowHeat((v) => !v)}
        />
        <input
          type="range"
          min={0.1}
          max={1}
          step={0.05}
          value={opacity}
          onChange={(event) => setOpacity(Number(event.target.value))}
          className="mx-1 h-1 w-16 cursor-pointer accent-[rgb(var(--accent))] disabled:opacity-40"
          disabled={!showHeat || !result}
          aria-label="Heat map opacity"
          title="Heat map opacity"
        />
        <ToolButton
          icon="target"
          label="Regions"
          shortcut="R"
          active={showRegions && !!result?.regions.length}
          onClick={() => setShowRegions((v) => !v)}
        />
        <span className="mx-1 h-5 w-px bg-white/10" />
        <ToolButton
          icon="reset"
          label="Reset zoom, window, and inversion"
          shortcut="0"
          onClick={reset}
        />
      </div>

      <div
        ref={container}
        className={`relative flex-1 touch-none select-none overflow-hidden ${
          tool === "window" ? "cursor-ns-resize" : "cursor-grab active:cursor-grabbing"
        }`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onPointerLeave={() => setCursor(null)}
        onDoubleClick={fit}
        onContextMenu={(event) => event.preventDefault()}
        data-testid="viewer"
      >
        {src && !failed && (
          <div
            className="absolute left-0 top-0 origin-top-left"
            style={{
              transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})`,
              width: size?.width,
              height: size?.height,
              visibility: size ? "visible" : "hidden",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- object URLs and the API's images */}
            <img
              key={src}
              src={src}
              alt="CT slice"
              crossOrigin="anonymous"
              draggable={false}
              onLoad={onLoad}
              onError={() => setFailed(true)}
              className="block max-w-none"
              style={{
                filter: `url(#${filterId})`,
                imageRendering: view.scale > 3 ? "pixelated" : "auto",
              }}
            />
            {result && heatBox && (
              <canvas
                ref={heatCanvas}
                className="pointer-events-none absolute transition-opacity duration-300"
                style={{
                  left: heatBox.x,
                  top: heatBox.y,
                  width: heatBox.width,
                  height: heatBox.height,
                  opacity: showHeat ? opacity : 0,
                  mixBlendMode: "screen",
                }}
                data-testid="heatmap"
              />
            )}
            {result && size && showRegions && result.regions.length > 0 && (
              <svg
                className="pointer-events-none absolute inset-0 overflow-visible"
                width={size.width}
                height={size.height}
                viewBox={`0 0 ${size.width} ${size.height}`}
              >
                {result.regions.map((region, k) => {
                  const active = highlight === region.id;
                  const dim = highlight && !active;
                  return (
                    <g key={region.id} opacity={dim ? 0.35 : 1}>
                      <circle
                        cx={region.x}
                        cy={region.y}
                        r={region.radius}
                        fill="none"
                        stroke="#67e8f9"
                        strokeWidth={active ? 3 : 1.75}
                        strokeDasharray={active ? undefined : "6 4"}
                        vectorEffect="non-scaling-stroke"
                      />
                      <g
                        transform={`translate(${region.x + region.radius * 0.72} ${region.y - region.radius * 0.72}) scale(${1 / view.scale})`}
                      >
                        <circle r={10} fill="#67e8f9" />
                        <text
                          textAnchor="middle"
                          dy="4"
                          fontSize="12"
                          fontWeight="700"
                          fill="#042f2e"
                        >
                          {k + 1}
                        </text>
                      </g>
                    </g>
                  );
                })}
              </svg>
            )}
            {scanning && (
              <div className="pointer-events-none absolute inset-0 overflow-hidden">
                <div className="absolute inset-0 bg-[linear-gradient(rgb(103_232_249/0.06)_1px,transparent_1px),linear-gradient(90deg,rgb(103_232_249/0.06)_1px,transparent_1px)] bg-[size:24px_24px]" />
                <div className="absolute inset-x-0 top-0 h-[10%] animate-sweep bg-gradient-to-b from-transparent via-cyan-300/45 to-transparent" />
              </div>
            )}
          </div>
        )}

        {!src && (
          <div className="absolute inset-0 grid place-items-center text-[12.5px] text-slate-500">
            No image
          </div>
        )}
        {failed && (
          <div className="absolute inset-0 grid place-items-center text-[12.5px] text-rose-300">
            The slice could not be loaded
          </div>
        )}

        <div className="pointer-events-none absolute inset-0 p-3 font-mono text-11 leading-[1.5] text-slate-300/90 [text-shadow:0_1px_2px_rgb(0_0_0/0.9)]">
          <div className="absolute left-3 top-3">
            {topLeft.map((line, i) => (
              <div key={i} className={i === 0 ? "font-semibold text-slate-100" : ""}>
                {line}
              </div>
            ))}
          </div>
          <div className="absolute right-3 top-3 text-right">
            {topRight.map((line, i) => (
              <div key={i}>{line}</div>
            ))}
            {size && (
              <div>
                {size.width} × {size.height} px
              </div>
            )}
          </div>
          <div className="absolute bottom-3 left-3">
            <div>Zoom {Math.round(view.scale * 100)}%</div>
            <div className={windowChanged ? "text-cyan-200" : ""}>
              W {Math.round(win.width)} L {Math.round(win.level)}
              {invert && " · inverted"}
            </div>
          </div>
          <div className="absolute bottom-3 right-3 text-right">
            {cursor ? (
              <>
                <div>
                  X {cursor.x} Y {cursor.y}
                  {!Number.isNaN(cursor.value) && ` · value ${cursor.value}`}
                </div>
                {cursor.heat !== null && (
                  <div className="text-amber-200">Grad-CAM {cursor.heat.toFixed(2)}</div>
                )}
              </>
            ) : (
              result &&
              showHeat && (
                <div className="flex items-center justify-end gap-2">
                  <span>Grad-CAM</span>
                  <span className="h-1.5 w-20 rounded-full" style={{ background: HEAT_GRADIENT }} />
                </div>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
