/** Types and calls for the Engram API. Requests go to /api, which Next.js forwards. */

export type Citation = {
  marker: number;
  document_path: string;
  source_name: string;
  heading_path: string[];
  start_line: number | null;
  end_line: number | null;
  page_start: number | null;
  page_end: number | null;
  revision: string | null;
  snippet: string;
  url: string | null;
};

export type Outcome =
  | "answered"
  | "insufficient_evidence"
  | "unverifiable"
  | "quota_exhausted"
  | "llm_error";

export type QuestionResponse = {
  id: string;
  outcome: Outcome;
  answer: string | null;
  citations: Citation[];
  passages: Citation[];
};

export type Source = {
  id: string;
  type: string;
  name: string;
  config: Record<string, unknown>;
};

export type JobStatus =
  | "pending"
  | "running"
  | "awaiting_embedding"
  | "succeeded"
  | "partial"
  | "failed"
  | "interrupted";

export type Job = {
  id: string;
  source_id: string;
  status: JobStatus;
  file_counts: { processed: number; skipped: number; failed: number };
  errors: { path: string; reason: string }[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

/** The API answered with an error status. Network failures stay as fetch's TypeError. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  return (await response.json()) as T;
}

/** FastAPI puts the reason in `detail`: a string, or an object with a `message`. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const detail = (await response.json())?.detail;
    if (typeof detail === "string") return detail;
    if (typeof detail?.message === "string") return detail.message;
  } catch {
    // The body wasn't JSON, so fall through to the status.
  }
  return `The server returned HTTP ${response.status}.`;
}

export function listSources(): Promise<Source[]> {
  return request<Source[]>("/api/sources");
}

export type GithubSourceInput = {
  name: string;
  repository: string;
  branch: string;
  include_paths: string[];
};

/** Add a GitHub repository as a source. Nothing is fetched until it is synced. */
export function createGithubSource(body: GithubSourceInput): Promise<Source> {
  return request<Source>("/api/sources", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Start a job that reads the source's newest commit, and return the job's id. A deferred
 * job stops at awaiting_embedding for the Kaggle notebook. */
export async function syncSource(id: string, deferEmbedding = false): Promise<string> {
  const query = deferEmbedding ? "?defer_embedding=true" : "";
  const accepted = await request<{ job_id: string }>(
    `/api/sources/${encodeURIComponent(id)}/sync${query}`,
    { method: "POST" },
  );
  return accepted.job_id;
}

/** Start an ingestion job for the files and return its id. */
export async function uploadFiles(
  sourceId: string,
  files: File[],
  deferEmbedding: boolean,
): Promise<string> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  form.append("defer_embedding", String(deferEmbedding));
  const accepted = await request<{ job_id: string }>(
    `/api/sources/${encodeURIComponent(sourceId)}/documents`,
    { method: "POST", body: form },
  );
  return accepted.job_id;
}

/** The newest 50 jobs, newest first. */
export function listJobs(): Promise<Job[]> {
  return request<Job[]>("/api/jobs");
}

export async function retryJob(id: string): Promise<void> {
  await request(`/api/jobs/${encodeURIComponent(id)}/retry`, { method: "POST" });
}

export function askQuestion(question: string): Promise<QuestionResponse> {
  return request<QuestionResponse>("/api/questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}
