// frontend/components/dashboard/UploadZone.tsx
"use client";

import { useState } from "react";

interface UploadZoneProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

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
      e.target.value = ""; // Reset input
    }
  };

  return (
    <div className="mb-8">
      <label className="block">
        <div className="border-2 border-dashed border-zinc-700 rounded-lg p-8 text-center hover:border-lapis-500/50 transition-colors cursor-pointer">
          <input
            type="file"
            accept=".pdf"
            onChange={handleChange}
            disabled={disabled || uploading}
            className="hidden"
          />
          <p className="text-zinc-300 mb-2">
            {uploading ? "Uploading..." : "Click to upload PDF"}
          </p>
          <p className="text-sm text-zinc-500">Maximum file size: 10MB</p>
        </div>
      </label>
    </div>
  );
}
