import { afterEach, expect, test, vi } from "vitest";

import { ApiError, createGithubSource, syncSource, uploadFiles } from "@/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(response: Response) {
  const fetchMock = vi.fn<typeof fetch>(async () => response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("uploadFiles posts the files and the embedding choice as a form", async () => {
  const fetchMock = stubFetch(Response.json({ job_id: "j1" }, { status: 202 }));
  const files = [new File(["# A"], "a.md"), new File(["# B"], "b.md")];
  expect(await uploadFiles("s 1", files, true)).toBe("j1");
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/sources/s%201/documents");
  expect(init?.method).toBe("POST");
  const form = init?.body as FormData;
  expect(form.getAll("files").map((file) => (file as File).name)).toEqual(["a.md", "b.md"]);
  expect(form.get("defer_embedding")).toBe("true");
});

test("createGithubSource posts the fields as JSON", async () => {
  const created = { id: "g", type: "github", name: "o/r", config: {} };
  const fetchMock = stubFetch(Response.json(created, { status: 201 }));
  const body = { name: "", repository: "o/r", branch: "main", include_paths: ["docs/**"] };
  expect(await createGithubSource(body)).toEqual(created);
  const [url, init] = fetchMock.mock.calls[0];
  expect([url, init?.method]).toEqual(["/api/sources", "POST"]);
  expect(new Headers(init?.headers).get("content-type")).toBe("application/json");
  expect(JSON.parse(init?.body as string)).toEqual(body);
});

test("syncSource starts a job and returns its id", async () => {
  const fetchMock = stubFetch(Response.json({ job_id: "j2" }, { status: 202 }));
  expect(await syncSource("g 1")).toBe("j2");
  const [url, init] = fetchMock.mock.calls[0];
  expect([url, init?.method]).toEqual(["/api/sources/g%201/sync", "POST"]);
});

test("an error detail object gives its message", async () => {
  stubFetch(
    Response.json({ detail: { message: "A job is already open", job_id: "j0" } }, { status: 409 }),
  );
  const error = await uploadFiles("s", [new File(["x"], "a.md")], false).catch((e) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect([error.status, error.message]).toEqual([409, "A job is already open"]);
});

test("an error without JSON names the status", async () => {
  stubFetch(new Response("Bad gateway", { status: 502 }));
  const error = await uploadFiles("s", [new File(["x"], "a.md")], false).catch((e) => e);
  expect(error.message).toBe("The server returned HTTP 502.");
});

test("syncSource can defer embedding to the Kaggle notebook", async () => {
  const fetchMock = stubFetch(Response.json({ job_id: "j3" }, { status: 202 }));
  await syncSource("g", true);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/sources/g/sync?defer_embedding=true");
});
