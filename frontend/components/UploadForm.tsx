"use client";

import { type FormEvent, useRef, useState } from "react";

import { ApiError, uploadFiles } from "@/lib/api";

export default function UploadForm({
  sourceId,
  onUploaded,
}: {
  sourceId: string;
  onUploaded: (jobId: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [deferEmbedding, setDeferEmbedding] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (files.length === 0 || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const jobId = await uploadFiles(sourceId, files, deferEmbedding);
      setFiles([]);
      if (input.current) input.current.value = "";
      onUploaded(jobId);
    } catch (failure) {
      setError(
        failure instanceof ApiError
          ? failure.message
          : "Couldn't reach Engram. Check your connection and that the app is still running.",
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <form className="upload" onSubmit={submit}>
      <label htmlFor="files">Files</label>
      <p className="hint" id="files-hint">
        Markdown, PDF or Word documents, up to 25 MB each.
      </p>
      <input
        ref={input}
        id="files"
        type="file"
        multiple
        accept=".md,.pdf,.docx"
        aria-describedby="files-hint"
        onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
      />
      <label className="checkbox">
        <input
          type="checkbox"
          checked={deferEmbedding}
          onChange={(event) => setDeferEmbedding(event.target.checked)}
        />
        Embed later with the Kaggle notebook
      </label>
      <button type="submit" className="ask-button" disabled={files.length === 0 || uploading}>
        {uploading ? "Uploading…" : "Upload"}
      </button>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
