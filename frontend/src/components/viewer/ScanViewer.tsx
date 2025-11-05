"use client";

/** Scan viewer component with nodule overlay visualization. */

import { useState } from "react";
import { Nodule } from "@/lib/types";
import NoduleOverlay from "./NoduleOverlay";

interface ScanViewerProps {
  imageUrl: string;
  nodules: Nodule[];
  onNoduleClick: (nodule: Nodule) => void;
}

export default function ScanViewer({
  imageUrl,
  nodules,
  onNoduleClick,
}: ScanViewerProps) {
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(
    null
  );
  const [imageError, setImageError] = useState(false);

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    console.log("Image loaded successfully:", img.naturalWidth, "x", img.naturalHeight);
    setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
    setImageError(false);
  };

  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    console.error("Image failed to load:", imageUrl);
    setImageError(true);
  };

  if (imageError) {
    return (
      <div className="relative w-full max-w-4xl mx-auto">
        <div className="border border-red-300 rounded-lg p-8 bg-red-50 text-center">
          <p className="text-red-600 font-semibold mb-2">Failed to load CT scan image</p>
          <p className="text-sm text-red-500 mb-4">URL: {imageUrl}</p>
          <p className="text-sm text-slate-600">Please check the console for more details.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full max-w-4xl mx-auto">
      <div className="relative border border-gray-300 rounded-lg overflow-hidden bg-gray-100">
        <img
          src={imageUrl}
          alt="CT Scan"
          onLoad={handleImageLoad}
          onError={handleImageError}
          className="w-full h-auto block"
          crossOrigin="anonymous"
        />
        {imageSize && (
          <NoduleOverlay
            nodules={nodules}
            imageWidth={imageSize.width}
            imageHeight={imageSize.height}
            onNoduleClick={onNoduleClick}
          />
        )}
      </div>
      <div className="mt-4 text-sm text-gray-600">
        Click on a nodule marker to view details
      </div>
    </div>
  );
}

