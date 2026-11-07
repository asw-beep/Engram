import { render, screen } from "@testing-library/react";
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
