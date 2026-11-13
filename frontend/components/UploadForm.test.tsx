import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import UploadForm from "@/components/UploadForm";
import * as api from "@/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

test("upload reports a rejected file", async () => {
  vi.spyOn(api, "uploadFiles").mockRejectedValue(new api.ApiError(413, "File too large"));
  render(<UploadForm sourceId="s" onUploaded={vi.fn()} />);
  await userEvent.upload(screen.getByLabelText(/files/i), new File(["x"], "a.md"));
  await userEvent.click(screen.getByRole("button", { name: /upload/i }));
  expect(await screen.findByText("File too large")).toBeInTheDocument();
});

test("dropped files are listed and uploaded, and unsupported types are left out", async () => {
  const upload = vi.spyOn(api, "uploadFiles").mockResolvedValue("job-1");
  render(<UploadForm sourceId="s" onUploaded={vi.fn()} />);
  const kept = new File(["x"], "a.md");
  const zone = screen.getByText(/drop files here/i).closest("div")!;
  fireEvent.drop(zone, { dataTransfer: { files: [kept, new File(["x"], "b.exe")] } });
  expect(screen.getByText("a.md")).toBeInTheDocument();
  expect(screen.queryByText("b.exe")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /upload/i }));
  expect(upload).toHaveBeenCalledWith("s", [kept], false);
});

test("dropping only unsupported files says so and keeps upload disabled", () => {
  render(<UploadForm sourceId="s" onUploaded={vi.fn()} />);
  const zone = screen.getByText(/drop files here/i).closest("div")!;
  fireEvent.drop(zone, { dataTransfer: { files: [new File(["x"], "b.exe")] } });
  expect(screen.getByRole("alert")).toHaveTextContent(/markdown, pdf or word/i);
  expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
});
