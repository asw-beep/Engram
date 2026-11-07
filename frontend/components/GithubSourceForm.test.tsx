import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import GithubSourceForm from "@/components/GithubSourceForm";
import * as api from "@/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

function source(): api.Source {
  return {
    id: "g",
    type: "github",
    name: "kubernetes/website",
    config: { repository: "kubernetes/website", branch: "main", include_paths: ["**"] },
  };
}

test("submits repository, branch and include paths", async () => {
  const create = vi.spyOn(api, "createGithubSource").mockResolvedValue(source());
  render(<GithubSourceForm onCreated={vi.fn()} />);
  await userEvent.type(screen.getByLabelText(/repository/i), "kubernetes/website");
  await userEvent.type(screen.getByLabelText(/include paths/i), "content/en/docs/concepts/**");
  await userEvent.click(screen.getByRole("button", { name: /add/i }));
  expect(create).toHaveBeenCalledWith({
    name: "",
    repository: "kubernetes/website",
    branch: "main",
    include_paths: ["content/en/docs/concepts/**"],
  });
});

test("each include line is one pattern, and blank lines are dropped", async () => {
  const create = vi.spyOn(api, "createGithubSource").mockResolvedValue(source());
  render(<GithubSourceForm onCreated={vi.fn()} />);
  await userEvent.type(screen.getByLabelText(/repository/i), "o/r");
  await userEvent.type(screen.getByLabelText(/include paths/i), " docs/** {Enter}{Enter}*.md");
  await userEvent.click(screen.getByRole("button", { name: /add/i }));
  expect(create).toHaveBeenCalledWith(
    expect.objectContaining({ include_paths: ["docs/**", "*.md"] }),
  );
});

test("the branch and display name can be changed", async () => {
  const create = vi.spyOn(api, "createGithubSource").mockResolvedValue(source());
  render(<GithubSourceForm onCreated={vi.fn()} />);
  await userEvent.type(screen.getByLabelText(/repository/i), "o/r");
  await userEvent.clear(screen.getByLabelText(/branch/i));
  await userEvent.type(screen.getByLabelText(/branch/i), "release-1.0");
  await userEvent.type(screen.getByLabelText(/display name/i), "Docs");
  await userEvent.click(screen.getByRole("button", { name: /add/i }));
  expect(create).toHaveBeenCalledWith(
    expect.objectContaining({ name: "Docs", branch: "release-1.0" }),
  );
});

test("a created source is passed on and the form is cleared", async () => {
  vi.spyOn(api, "createGithubSource").mockResolvedValue(source());
  const onCreated = vi.fn();
  render(<GithubSourceForm onCreated={onCreated} />);
  await userEvent.type(screen.getByLabelText(/repository/i), "kubernetes/website");
  await userEvent.type(screen.getByLabelText(/branch/i), "-next");
  await userEvent.type(screen.getByLabelText(/include paths/i), "docs/**");
  await userEvent.type(screen.getByLabelText(/display name/i), "Docs");
  await userEvent.click(screen.getByRole("button", { name: /add/i }));
  expect(onCreated).toHaveBeenCalledWith(source());
  expect(screen.getByLabelText(/repository/i)).toHaveValue("");
  expect(screen.getByLabelText(/branch/i)).toHaveValue("main");
  expect(screen.getByLabelText(/include paths/i)).toHaveValue("");
  expect(screen.getByLabelText(/display name/i)).toHaveValue("");
});

test("nothing is sent without a repository", async () => {
  const create = vi.spyOn(api, "createGithubSource");
  render(<GithubSourceForm onCreated={vi.fn()} />);
  expect(screen.getByRole("button", { name: /add/i })).toBeDisabled();
  await userEvent.type(screen.getByLabelText(/repository/i), "   ");
  expect(screen.getByRole("button", { name: /add/i })).toBeDisabled();
  expect(create).not.toHaveBeenCalled();
});

test("a rejected repository shows the API's reason", async () => {
  vi.spyOn(api, "createGithubSource").mockRejectedValue(
    new api.ApiError(422, "Enter a GitHub repository as owner/name, or paste its URL"),
  );
  const onCreated = vi.fn();
  render(<GithubSourceForm onCreated={onCreated} />);
  await userEvent.type(screen.getByLabelText(/repository/i), "nope");
  await userEvent.click(screen.getByRole("button", { name: /add/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("owner/name");
  expect(onCreated).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/repository/i)).toHaveValue("nope");
});
