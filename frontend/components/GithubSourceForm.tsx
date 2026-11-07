"use client";

import { type FormEvent, useState } from "react";

import { ApiError, createGithubSource, type Source } from "@/lib/api";

const DEFAULT_BRANCH = "main";

export default function GithubSourceForm({ onCreated }: { onCreated: (source: Source) => void }) {
  const [repository, setRepository] = useState("");
  const [branch, setBranch] = useState(DEFAULT_BRANCH);
  const [includePaths, setIncludePaths] = useState("");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = repository.trim() !== "" && !saving;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setSaving(true);
    setError(null);
    try {
      const source = await createGithubSource({
        name: name.trim(),
        repository: repository.trim(),
        branch: branch.trim(),
        include_paths: includePaths
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line !== ""),
      });
      setRepository("");
      setBranch(DEFAULT_BRANCH);
      setIncludePaths("");
      setName("");
      onCreated(source);
    } catch (failure) {
      setError(
        failure instanceof ApiError
          ? failure.message
          : "Couldn't reach Engram. Check your connection and that the app is still running.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="github-form" onSubmit={submit}>
      <div className="field">
        <label htmlFor="github-repository">Repository</label>
        <p className="hint" id="github-repository-hint">
          owner/name, or the repository&apos;s URL. Private repositories need a GITHUB_TOKEN on
          the server.
        </p>
        <input
          id="github-repository"
          className="code-input"
          value={repository}
          onChange={(event) => setRepository(event.target.value)}
          placeholder="kubernetes/website"
          aria-describedby="github-repository-hint"
          autoComplete="off"
          spellCheck={false}
        />
      </div>
      <div className="field field-short">
        <label htmlFor="github-branch">Branch</label>
        <input
          id="github-branch"
          className="code-input"
          value={branch}
          onChange={(event) => setBranch(event.target.value)}
          autoComplete="off"
          spellCheck={false}
        />
      </div>
      <div className="field">
        <label htmlFor="github-include">Include paths</label>
        <p className="hint" id="github-include-hint">
          One pattern per line. ** matches any number of folders and * stays within one. Leave it
          empty to read the whole repository. Only Markdown, PDF and Word files are read.
        </p>
        <textarea
          id="github-include"
          className="code-input"
          rows={3}
          value={includePaths}
          onChange={(event) => setIncludePaths(event.target.value)}
          placeholder="docs/**"
          aria-describedby="github-include-hint"
          spellCheck={false}
        />
      </div>
      <div className="field">
        <label htmlFor="github-name">
          Display name <span className="label-note">(optional, defaults to owner/name)</span>
        </label>
        <input
          id="github-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="off"
        />
      </div>
      <button type="submit" className="ask-button" disabled={!ready}>
        {saving ? "Adding…" : "Add repository"}
      </button>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
