"use client";

/** File dropzone component for uploading CT scan images. */

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface FileDropzoneProps {
  onFileSelect: (file: File) => void;
}

export default function FileDropzone({ onFileSelect }: FileDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const file = e.dataTransfer.files[0];
      if (file && isImageFile(file)) {
        onFileSelect(file);
      } else {
        alert("Please upload a valid image file (JPEG, PNG, or DICOM)");
      }
    },
    [onFileSelect]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file && isImageFile(file)) {
        onFileSelect(file);
      } else {
        alert("Please upload a valid image file (JPEG, PNG, or DICOM)");
      }
    },
    [onFileSelect]
  );

  const isImageFile = (file: File): boolean => {
    const validTypes = [
      "image/jpeg",
      "image/jpg",
      "image/png",
      "image/dicom",
      "application/dicom",
    ];
    return validTypes.includes(file.type.toLowerCase());
  };

  return (
    <motion.div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.3 }}
      className={`border-2 border-dashed rounded-xl p-12 lg:p-16 text-center transition-all duration-200 ${
        isDragging
          ? "border-primary-500 bg-gradient-to-br from-primary-50 to-blue-50"
          : "border-slate-300 bg-slate-50 hover:border-primary-400 hover:bg-slate-100/50"
      }`}
    >
      <motion.div
        animate={isDragging ? { scale: 1.15, rotate: [0, -5, 5, -5, 0] } : { scale: 1 }}
        transition={{ duration: 0.3 }}
      >
        <input
          type="file"
          id="file-upload"
          accept="image/jpeg,image/png,image/dicom,application/dicom"
          onChange={handleFileInput}
          className="hidden"
        />
        <label
          htmlFor="file-upload"
          className="cursor-pointer flex flex-col items-center"
        >
          <motion.div
            className="mb-6"
            whileHover={{ scale: 1.1 }}
            transition={{ type: "spring", stiffness: 300 }}
          >
            <AnimatePresence mode="wait">
              <motion.svg
                key={isDragging ? "dragging" : "idle"}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={{ duration: 0.2 }}
                className={`w-16 h-16 ${isDragging ? "text-primary-600" : "text-slate-400"}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </motion.svg>
            </AnimatePresence>
          </motion.div>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-xl font-semibold text-slate-900 mb-2"
          >
            Drop your CT scan here or click to browse
          </motion.p>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-sm text-slate-600"
          >
            Supports JPEG, PNG, and DICOM formats
          </motion.p>
        </label>
      </motion.div>
    </motion.div>
  );
}

