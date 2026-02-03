/**
 * Upload zone: click-to-select area for PDF uploads. Parent handles the actual
 * API call via onUpload; this component only handles file pick and loading state.
 */
"use client";

import { useState } from "react";

interface UploadZoneProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

/**
 * Renders a dashed-border area that opens the file picker. Accepts PDF only;
 * shows "Uploading..." while onUpload is in progress.
 */
function isPdf(file: File): boolean {
  return (
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  );
}

export function UploadZone({ onUpload, disabled }: UploadZoneProps) {
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const uploadFile = async (file: File) => {
    setUploading(true);
    try {
      await onUpload(file);
    } finally {
      setUploading(false);
    }
  };

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !isPdf(file)) return;
    await uploadFile(file);
    e.target.value = ""; // Allow selecting the same file again
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (!file || !isPdf(file)) return;
    await uploadFile(file);
  };

  return (
    <div className="mb-4">
      <label className="block relative cursor-pointer rounded-lg outline-none focus-within:ring-2 focus-within:ring-lapis-500 focus-within:ring-offset-2 focus-within:ring-offset-zinc-900">
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
            isDragging
              ? "border-lapis-500 bg-lapis-500/10"
              : "border-zinc-700 hover:border-lapis-500/50"
          }`}
        >
          <input
            type="file"
            accept=".pdf"
            onChange={handleChange}
            disabled={disabled || uploading}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
            aria-label="Upload PDF"
          />
          <p className="text-zinc-300 text-body-sm mb-1">
            {uploading ? "Uploading..." : "Upload PDF or drag a file here"}
          </p>
          <p className="text-helper">Max 10MB</p>
        </div>
      </label>
    </div>
  );
}
