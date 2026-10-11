"use client";

import React, { useRef, useState } from "react";
import { UploadCloud, FileArchive, X, ArrowRight, Loader2, AlertCircle } from "lucide-react";
import { uploadZipRepository, ApiError } from "@/lib/api";
import { IngestResponse } from "@/lib/types";

interface ZipDropzoneProps {
  onSuccess: (response: IngestResponse) => void;
  onError: (errorMessage: string) => void;
}

export const ZipDropzone: React.FC<ZipDropzoneProps> = ({ onSuccess, onError }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): boolean => {
    setValidationError(null);

    // Format check
    if (!file.name.toLowerCase().endsWith(".zip")) {
      const err = "Only .zip archive files are supported.";
      setValidationError(err);
      onError(err);
      return false;
    }

    // Size limit check (100 MB)
    const maxBytes = 100 * 1024 * 1024;
    if (file.size > maxBytes) {
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      const err = `File size (${sizeMb} MB) exceeds maximum allowed limit of 100 MB.`;
      setValidationError(err);
      onError(err);
      return false;
    }

    return true;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
      }
    }
  };

  const handleRemove = () => {
    setSelectedFile(null);
    setValidationError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setValidationError(null);

    try {
      const response = await uploadZipRepository(selectedFile);
      onSuccess(response);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to upload ZIP archive.";
      onError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const formatSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".zip,application/zip"
        onChange={handleFileChange}
        className="hidden"
        id="zip-upload-input"
      />

      {/* Drop area */}
      {!selectedFile ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 ${
            isDragging
              ? "border-[#0B6E5F] bg-[#E6F4F1]/60 scale-[1.01]"
              : "border-[#D6D2CA] hover:border-[#0B6E5F] hover:bg-[#F9F8F6] bg-white"
          }`}
        >
          <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center">
            <UploadCloud className="w-7 h-7" />
          </div>
          <h3 className="text-base font-semibold text-[#1C2024] mb-1">
            Drag & drop your repository ZIP here
          </h3>
          <p className="text-xs text-[#636A74] mb-4">
            Supports codebase archives up to 100 MB (source code only)
          </p>
          <button
            type="button"
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#1C2024] text-white hover:bg-black transition-colors"
          >
            Browse Local File
          </button>
        </div>
      ) : (
        /* Selected file card */
        <div className="border border-[#E5E2DB] rounded-xl p-5 bg-white shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center">
                <FileArchive className="w-5 h-5" />
              </div>
              <div>
                <p className="text-sm font-semibold text-[#1C2024] truncate max-w-sm">
                  {selectedFile.name}
                </p>
                <p className="text-xs text-[#636A74]">
                  {formatSize(selectedFile.size)} • ZIP archive
                </p>
              </div>
            </div>
            {!isUploading && (
              <button
                type="button"
                onClick={handleRemove}
                className="p-1.5 text-[#636A74] hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="Remove file"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <button
            type="button"
            disabled={isUploading}
            onClick={handleSubmit}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-[#0B6E5F] hover:bg-[#085449] disabled:bg-[#0B6E5F]/60 text-white font-medium text-sm transition-colors shadow-sm"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Uploading & Unpacking...</span>
              </>
            ) : (
              <>
                <span>Upload & Start Indexing</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      )}

      {/* Validation error callout */}
      {validationError && (
        <div className="flex items-center gap-2 p-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{validationError}</span>
        </div>
      )}
    </div>
  );
};
