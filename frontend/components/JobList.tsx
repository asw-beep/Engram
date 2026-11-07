import type { Job, JobStatus } from "@/lib/api";

const RETRYABLE: JobStatus[] = ["partial", "failed", "interrupted"];

export default function JobList({ jobs, onRetry }: { jobs: Job[]; onRetry: (id: string) => void }) {
  if (jobs.length === 0) {
    return <p className="hint">No uploads yet. Files you upload appear here while they are processed.</p>;
  }
  return (
    <ul className="jobs">
      {jobs.map((job) => (
        <li key={job.id} className="job">
          <div className="job-summary">
            <span className={`job-status status-${job.status}`}>{job.status.replaceAll("_", " ")}</span>
            <span className="job-counts">{counts(job)}</span>
            <time className="job-time" dateTime={job.created_at}>
              {new Date(job.created_at).toLocaleString()}
            </time>
            {RETRYABLE.includes(job.status) && (
              <button type="button" className="retry-button" onClick={() => onRetry(job.id)}>
                Retry
              </button>
            )}
          </div>
          {job.errors.length > 0 && (
            <ul className="job-errors">
              {job.errors.map((error, index) => (
                <li key={index}>{error.path ? `${error.path}: ${error.reason}` : error.reason}</li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

function counts({ file_counts: { processed, skipped, failed } }: Job): string {
  return `${processed} processed, ${skipped} unchanged, ${failed} failed`;
}
