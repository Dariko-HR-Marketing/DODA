import { test, expect } from "@playwright/test";
import { requiredEnv } from "./env";

// Deliberately its own seed run (E2E_KNOWLEDGE_ prefix) — this spec
// uploads and deletes real Document rows, and a shared seed with another
// spec that lists documents (there currently is none, but the same
// "each mutating spec gets its own seed" convention as
// workspace-kill-switch.spec.ts/logout.spec.ts applies here too).
const SESSION_ID = requiredEnv("E2E_KNOWLEDGE_SESSION_ID");
const WORKSPACE_ID = requiredEnv("E2E_KNOWLEDGE_WORKSPACE_ID");

test.describe.configure({ mode: "serial" });

test("FR-KNW-001: upload, list, download, reject, and delete a file", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  await test.step("log in and open the seeded workspace", async () => {
    await page.goto("/login");
    await page.fill("#session-id", SESSION_ID);
    await page.click('button[type="submit"]');
    await page.waitForURL("**/workspaces");
    await page.getByText("Demo Workspace").click();
    await page.waitForURL(`**/workspaces/${WORKSPACE_ID}`);
  });

  await test.step("upload a real PDF and see it in the file list", async () => {
    await page.setInputFiles('input[aria-label="Yuklanadigan fayl"]', {
      name: "report.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n%\xe2\xe3\xcf\xd3\nE2E test pdf body"),
    });
    await page.click('form:has(input[aria-label="Yuklanadigan fayl"]) button[type="submit"]');
    await expect(page.getByTestId("document-list").getByText("report.pdf")).toBeVisible();
  });

  await test.step("downloading it round-trips the exact bytes via the real backend", async () => {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("document-list").getByText("Yuklab olish").click(),
    ]);
    const path = await download.path();
    const fs = await import("node:fs/promises");
    const content = path ? await fs.readFile(path) : Buffer.alloc(0);
    expect(content.toString("utf-8")).toContain("E2E test pdf body");
  });

  await test.step("a Windows executable disguised as a .pdf is rejected, not stored", async () => {
    await page.setInputFiles('input[aria-label="Yuklanadigan fayl"]', {
      name: "invoice.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("MZ\x90\x00\x03\x00\x00\x00this is really an executable"),
    });
    await page.click('form:has(input[aria-label="Yuklanadigan fayl"]) button[type="submit"]');
    await expect(page.getByTestId("document-list").getByText("invoice.pdf")).toHaveCount(0);
    // The first, real upload is still the only entry.
    await expect(page.getByTestId("document-list").locator("li")).toHaveCount(1);
  });

  await test.step("FR-KNW-003 search: either a real hybrid-search hit or an honest not-configured error", async () => {
    // Whether an embedding provider is configured varies by environment
    // (CI never sets one; a developer's own .env might) — this probes
    // the real backend directly first, then asserts the UI path that
    // environment actually takes, rather than assuming either one.
    const probe = await page.request.get(
      `http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/documents/search?q=test`,
      { headers: { Authorization: `Bearer ${SESSION_ID}` } },
    );

    if (probe.status() === 503) {
      await page.fill('input[aria-label="Fayllar ichidan qidirish"]', "anything");
      await page.click('form:has(input[aria-label="Fayllar ichidan qidirish"]) button[type="submit"]');
      await expect(page.getByText("embedding provayderi sozlanmagan")).toBeVisible();
      return;
    }

    // Embedding IS configured here — a genuinely plain-text upload (the
    // .pdf uploaded above has no real PDF structure past its magic
    // bytes, so FR-KNW-002's extractor finds no text in it and it was
    // never indexed; a .txt needs no parser and always is).
    const needle = "e2e-retrieval-needle-7731";
    await page.setInputFiles('input[aria-label="Yuklanadigan fayl"]', {
      name: "searchable.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(`This note mentions ${needle} for the search test.`),
    });
    await page.click('form:has(input[aria-label="Yuklanadigan fayl"]) button[type="submit"]');
    await expect(page.getByTestId("document-list").getByText("searchable.txt")).toBeVisible();

    await page.fill('input[aria-label="Fayllar ichidan qidirish"]', needle);
    await page.click('form:has(input[aria-label="Fayllar ichidan qidirish"]) button[type="submit"]');
    await expect(page.getByTestId("document-search-results")).toContainText(needle);
    await page.click("text=Tozalash");
    await expect(page.getByTestId("document-search-results")).toHaveCount(0);

    await page
      .getByTestId("document-list")
      .locator("li")
      .filter({ hasText: "searchable.txt" })
      .getByText("O'chirish")
      .click();
    await expect(page.getByTestId("document-list").getByText("searchable.txt")).toHaveCount(0);
  });

  await test.step("delete removes it from the list", async () => {
    await page.getByTestId("document-list").getByText("O'chirish").click();
    await expect(page.getByTestId("document-list").getByText("Hali fayl yo'q.")).toBeVisible();
  });

  // The rejected-upload step above causes the browser to log the 422
  // response to console (a failed fetch, same as auditor.spec.ts's
  // expected-403 case) — that one line is expected, anything else is not.
  // A 503 from the search step (no embedding provider configured) is the
  // same kind of expected, non-UI-breaking failed fetch.
  const unexpected = consoleErrors.filter((text) => !text.includes("422") && !text.includes("503"));
  expect(unexpected).toEqual([]);
});

test("FR-KNW-009: a new version supersedes the old one, which stays downloadable", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  await test.step("log in and open the seeded workspace", async () => {
    await page.goto("/login");
    await page.fill("#session-id", SESSION_ID);
    await page.click('button[type="submit"]');
    await page.waitForURL("**/workspaces");
    await page.getByText("Demo Workspace").click();
    await page.waitForURL(`**/workspaces/${WORKSPACE_ID}`);
  });

  await test.step("upload the first version", async () => {
    await page.setInputFiles('input[aria-label="Yuklanadigan fayl"]', {
      name: "policy.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("v1 content"),
    });
    await page.click('form:has(input[aria-label="Yuklanadigan fayl"]) button[type="submit"]');
    await expect(page.getByTestId("document-list").getByText("policy.txt")).toBeVisible();
  });

  await test.step("upload a new version and see the old one marked superseded", async () => {
    await page
      .getByTestId("document-list")
      .locator("li")
      .filter({ hasText: "policy.txt" })
      .getByText("Yangi versiya yuklash")
      .click();
    await page.setInputFiles('input[aria-label="Yangi versiya fayli"]', {
      name: "policy-v2.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("v2 content"),
    });
    await expect(page.getByTestId("document-list").getByText("policy-v2.txt")).toBeVisible();
    await expect(page.getByTestId("document-superseded-badge")).toBeVisible();
    // The superseded row no longer offers "Yangi versiya yuklash" (only
    // the current tip of its own version chain may be versioned again —
    // create_document_version's own DocumentAlreadySupersededError).
    await expect(
      page.getByTestId("document-list").locator("li").filter({ hasText: "policy.txt" }).getByText("Yangi versiya yuklash"),
    ).toHaveCount(0);
  });

  await test.step("the superseded version is still downloadable, byte-for-byte", async () => {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page
        .getByTestId("document-list")
        .locator("li")
        .filter({ hasText: "policy.txt" })
        .getByText("Yuklab olish")
        .click(),
    ]);
    const path = await download.path();
    const fs = await import("node:fs/promises");
    const content = path ? await fs.readFile(path) : Buffer.alloc(0);
    expect(content.toString("utf-8")).toBe("v1 content");
  });

  await test.step("clean up both documents", async () => {
    await page
      .getByTestId("document-list")
      .locator("li")
      .filter({ hasText: "policy-v2.txt" })
      .getByText("O'chirish")
      .click();
    await expect(page.getByTestId("document-list").getByText("policy-v2.txt")).toHaveCount(0);
    await page
      .getByTestId("document-list")
      .locator("li")
      .filter({ hasText: "policy.txt" })
      .getByText("O'chirish")
      .click();
    await expect(page.getByTestId("document-list").getByText("Hali fayl yo'q.")).toBeVisible();
  });

  expect(consoleErrors).toEqual([]);
});
