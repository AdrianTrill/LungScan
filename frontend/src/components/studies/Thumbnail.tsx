"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Case } from "@/lib/types";

export default function Thumbnail({
  study,
  className = "h-11 w-11",
}: {
  study: Case;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api
      .imageUrl(study)
      .then((url) => live && setSrc(url))
      .catch(() => live && setSrc(null));
    return () => {
      live = false;
    };
  }, [study]);
  return (
    <span
      className={`relative block flex-none overflow-hidden rounded-lg border border-line bg-viewer ${className}`}
    >
      {src && (
        // eslint-disable-next-line @next/next/no-img-element -- object URLs and the API's images
        <img src={src} alt="" className="h-full w-full object-cover opacity-90" loading="lazy" />
      )}
      {study.flagged && (
        <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-flag ring-2 ring-black/60" />
      )}
    </span>
  );
}
