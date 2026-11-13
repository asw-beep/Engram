"use client";

import { type DragEvent, type FormEvent, useRef, useState } from "react";

import { ApiError, uploadFiles } from "@/lib/api";

const ACCEPTED = [".md", ".pdf", ".docx"];

function accepted(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED.some((extension) => name.endsWith(extension));
}

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
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Keep the supported files and say which ones were left out. */
  function choose(chosen: File[]) {
    const kept = chosen.filter(accepted);
    const dropped = chosen.filter((file) => !accepted(file));
    setFiles(kept);
    setError(
      dropped.length === 0
        ? null
        : `${dropped.map((file) => file.name).join(", ")} ${dropped.length === 1 ? "was" : "were"} left out. Only Markdown, PDF or Word files can be uploaded.`,
    );
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (uploading) return;
    // The file input can't hold dropped files, so clear it and keep them in state.
    if (input.current) input.current.value = "";
    choose(Array.from(event.dataTransfer.files));
  }

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
      <div
        className="dropzone"
        data-dragging={dragging}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <label htmlFor="files">Files</label>
        <p className="dropzone-prompt">Drop files here, or choose them.</p>
        <p className="hint" id="files-hint">
          Markdown, PDF or Word documents, up to 25 MB each.
        </p>
        <input
          ref={input}
          id="files"
          type="file"
          multiple
          accept={ACCEPTED.join(",")}
          aria-describedby="files-hint"
          onChange={(event) => choose(Array.from(event.target.files ?? []))}
        />
      </div>
      {files.length > 0 && (
        <ul className="chosen-files" aria-label="Chosen files">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>{file.name}</li>
          ))}
        </ul>
      )}
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
