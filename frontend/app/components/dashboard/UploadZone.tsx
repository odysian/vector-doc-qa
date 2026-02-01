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
export function UploadZone({ onUpload, disabled }: UploadZoneProps) {
  const [uploading, setUploading] = useState(false);

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      await onUpload(file);
    } finally {
      setUploading(false);
      e.target.value = ""; // Allow selecting the same file again
    }
  };

  return (
    <div className="mb-4">
      <label className="block relative cursor-pointer rounded-lg outline-none focus-within:ring-2 focus-within:ring-lapis-500 focus-within:ring-offset-2 focus-within:ring-offset-zinc-900">
        <div className="relative border-2 border-dashed border-zinc-700 rounded-lg p-4 text-center hover:border-lapis-500/50 transition-colors">
          <input
            type="file"
            accept=".pdf"
            onChange={handleChange}
            disabled={disabled || uploading}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
            aria-label="Upload PDF"
          />
          <p className="text-zinc-300 text-body-sm mb-1">
            {uploading ? "Uploading..." : "Upload PDF"}
          </p>
          <p className="text-helper">Max 10MB</p>
        </div>
      </label>
    </div>
  );
}
