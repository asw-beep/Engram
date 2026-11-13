"use client";

import { useCallback, useEffect, useState } from "react";

import GithubSourceForm from "@/components/GithubSourceForm";
import JobList from "@/components/JobList";
import UploadForm from "@/components/UploadForm";
import {
  ApiError,
  type Job,
  listJobs,
  listSources,
  retryJob,
  type Source,
  syncSource,
} from "@/lib/api";

const POLL_MS = 3000;

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deferSync, setDeferSync] = useState(false);

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

  async function sync(id: string) {
    setError(null);
    try {
      await syncSource(id, deferSync);
    } catch (failure) {
      setError(describeError(failure));
    }
    await refreshJobs();
  }

  const uploads = sources?.find((source) => source.type === "upload");
  const sourceNames = Object.fromEntries((sources ?? []).map((source) => [source.id, source.name]));

  return (
    <main className="page">
      <p className="label page-kicker">Ingestion</p>
      <h1 className="page-title">Sources</h1>
      <p className="lede">
        Upload documents or connect a GitHub repository to make them searchable. Processing runs in
        the background, and this page updates while a job is running.
      </p>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}

      <div className="source-panels">
        <section className="panel source-panel">
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

        <section className="panel source-panel">
          <h2>Connect a GitHub repository</h2>
          <GithubSourceForm
            onCreated={(source) => {
              setError(null);
              setSources((current) => [...(current ?? []), source]);
            }}
          />
        </section>
      </div>

      <section className="section">
        <h2>Recent jobs</h2>
        <JobList jobs={jobs} sourceNames={sourceNames} onRetry={(id) => void retry(id)} />
      </section>

      {sources && sources.length > 0 && (
        <section className="section">
          <h2>Connected sources</h2>
          <label className="checkbox sources-option">
            <input
              type="checkbox"
              checked={deferSync}
              onChange={(event) => setDeferSync(event.target.checked)}
            />
            Embed syncs later with the Kaggle notebook
          </label>
          <ul className="sources">
            {sources.map((source) => (
              <li key={source.id} className="source">
                <span className="source-name">{source.name}</span>
                <span className="source-detail">{describeSource(source)}</span>
                {source.type === "github" && (
                  <button
                    type="button"
                    className="small-button"
                    aria-label={`Sync ${source.name}`}
                    onClick={() => void sync(source.id)}
                  >
                    Sync
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function describeSource(source: Source): string {
  if (source.type === "upload") return "Uploaded files";
  if (source.type === "github") {
    const { repository, branch } = source.config as { repository?: string; branch?: string };
    return `GitHub repository ${repository ?? "unknown"}, branch ${branch ?? "unknown"}`;
  }
  return source.type;
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
