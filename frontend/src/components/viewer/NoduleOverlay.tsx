/** Overlay component for drawing nodule markers on the scan image. */

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Nodule } from "@/lib/types";

interface NoduleOverlayProps {
  nodules: Nodule[];
  imageWidth: number;
  imageHeight: number;
  onNoduleClick: (nodule: Nodule) => void;
}

export default function NoduleOverlay({
  nodules,
  imageWidth,
  imageHeight,
  onNoduleClick,
}: NoduleOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [displaySize, setDisplaySize] = useState({ width: imageWidth, height: imageHeight });

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const img = containerRef.current.parentElement?.querySelector("img");
        if (img) {
          setDisplaySize({ width: img.clientWidth, height: img.clientHeight });
        }
      }
    };

    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  const scaleX = displaySize.width / imageWidth;
  const scaleY = displaySize.height / imageHeight;

  const getColorForScore = (score: number): string => {
    if (score >= 0.8) return "red";
    if (score >= 0.6) return "orange";
    if (score >= 0.3) return "yellow";
    return "green";
  };

  return (
    <div
      ref={containerRef}
      className="absolute top-0 left-0 pointer-events-none"
      style={{
        width: `${displaySize.width}px`,
        height: `${displaySize.height}px`,
      }}
    >
      {nodules.map((nodule) => {
        const x = nodule.x * scaleX;
        const y = nodule.y * scaleY;
        const radius = nodule.radius * Math.min(scaleX, scaleY);
        const color = getColorForScore(nodule.malignancy_score);

        return (
          <motion.div
            key={nodule.id}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ 
              delay: Math.random() * 0.3,
              type: "spring",
              stiffness: 300,
              damping: 20
            }}
            whileHover={{ scale: 1.2, zIndex: 10 }}
            whileTap={{ scale: 0.9 }}
            className="absolute pointer-events-auto cursor-pointer"
            style={{
              left: `${x - radius}px`,
              top: `${y - radius}px`,
              width: `${radius * 2}px`,
              height: `${radius * 2}px`,
            }}
            onClick={() => onNoduleClick(nodule)}
          >
            <motion.div
              className="absolute rounded-full border-2"
              animate={{
                scale: [1, 1.1, 1],
                opacity: [0.6, 0.8, 0.6],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
              style={{
                width: "100%",
                height: "100%",
                borderColor: color,
                backgroundColor: `${color}20`,
              }}
            />
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2, type: "spring" }}
              className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-xs font-bold px-1 rounded"
              style={{
                backgroundColor: color,
                color: "white",
              }}
            >
              {(nodule.malignancy_score * 100).toFixed(0)}
            </motion.div>
          </motion.div>
        );
      })}
    </div>
  );
}

