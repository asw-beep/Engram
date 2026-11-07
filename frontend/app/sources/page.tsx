"use client";

import { useCallback, useEffect, useState } from "react";

import JobList from "@/components/JobList";
import UploadForm from "@/components/UploadForm";
import { ApiError, type Job, listJobs, listSources, retryJob, type Source } from "@/lib/api";

const POLL_MS = 3000;

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refreshJobs = useCallback(async () => {
    try {
      setJobs(await listJobs());
    } catch (failure) {
      setError(describeError(failure));
    }
  }, []);

  useEffect(() => {
    const fail = (failure: unknown) => setError(describeError(failure));
    listSources().then(setSources, fail);
    listJobs().then(setJobs, fail);
  }, []);

  // Poll only while a job is moving. A job awaiting embedding waits for the Kaggle import.
  const active = jobs.some((job) => job.status === "pending" || job.status === "running");
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void refreshJobs(), POLL_MS);
    return () => clearInterval(timer);
  }, [active, refreshJobs]);

  async function retry(id: string) {
    setError(null);
    try {
      await retryJob(id);
    } catch (failure) {
      setError(describeError(failure));
    }
    await refreshJobs();
  }

  const uploads = sources?.find((source) => source.type === "upload");

  return (
    <main className="page">
      <h1 className="page-title">Sources</h1>
      <p className="lede">
        Upload documents to make them searchable. Processing runs in the background, and this page
        updates while a job is running.
      </p>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}

      <section className="section">
        <h2>Upload documents</h2>
        {uploads ? (
          <UploadForm
            sourceId={uploads.id}
            onUploaded={() => {
              setError(null);
              void refreshJobs();
            }}
          />
        ) : (
          sources && <p className="hint">There is no upload source for this workspace.</p>
        )}
      </section>

      <section className="section">
        <h2>Recent jobs</h2>
        <JobList jobs={jobs} onRetry={(id) => void retry(id)} />
      </section>

      {sources && sources.length > 0 && (
        <section className="section">
          <h2>Connected sources</h2>
          <ul className="sources">
            {sources.map((source) => (
              <li key={source.id}>
                {source.name} <span className="hint">({source.type})</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status >= 500 && error.status !== 503) {
      return `The Engram API didn't answer (HTTP ${error.status}). Check that the backend is running on port 8000, then try again.`;
    }
    return error.message;
  }
  return "Couldn't reach Engram. Check your connection and that the app is still running.";
}
