import { test, expect } from "@playwright/test";
import { requiredEnv } from "./env";

// Deliberately its own seed run (E2E_CHAT_ prefix) — this spec toggles
// customer-wide AI provider/fallback settings, which every other spec's
// seeded customer would otherwise also see (the same "don't share mutable
// state across specs" lesson as workspace-kill-switch.spec.ts's own seed).
const SESSION_ID = requiredEnv("E2E_CHAT_SESSION_ID");
const WORKSPACE_ID = requiredEnv("E2E_CHAT_WORKSPACE_ID");
const CUSTOMER_ID = requiredEnv("E2E_CHAT_CUSTOMER_ID");

test.describe.configure({ mode: "serial" });

test("chat: send a message, get the real NullModelGateway reply, pin a provider", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  await test.step("log in and open the workspace's chat page", async () => {
    await page.goto("/login");
    await page.fill("#session-id", SESSION_ID);
    await page.click('button[type="submit"]');
    await page.waitForURL("**/workspaces");
    await page.goto(`/workspaces/${WORKSPACE_ID}/chat`);
    await expect(page.getByText("Yangi suhbat")).toBeVisible();
  });

  await test.step("start a new conversation", async () => {
    await page.click('button:has-text("Yangi suhbat")');
    await expect(page.getByPlaceholder("Xabar yozing...")).toBeVisible();
  });

  await test.step("sending a message streams a real reply over SSE from the running backend", async () => {
    await page.fill('input[placeholder="Xabar yozing..."]', "Salom, DODA!");
    await page.click('button:has-text("Yuborish")');
    await expect(page.getByText("Salom, DODA!")).toBeVisible();
    // No real provider credential exists in CI — this is the honest
    // NullModelGateway degradation text (doda.ai.port), proving the whole
    // pipeline (SSE stream -> persisted Message -> refetch) is real, not a
    // hardcoded frontend string.
    await expect(
      page.getByText("AI javob provayderi hali tanlanmagan yoki sozlanmagan"),
    ).toBeVisible();
  });

  await test.step("editing the latest message regenerates without deleting the original (FR-CONV-007)", async () => {
    await page.click('button:has-text("Tahrirlash")');
    await expect(page.getByText("Oxirgi xabaringizni tahrirlayapsiz")).toBeVisible();
    await expect(page.getByPlaceholder("Xabar yozing...")).toHaveValue("Salom, DODA!");

    await page.fill('input[placeholder="Xabar yozing..."]', "Salom, DODA! (tahrirlangan)");
    await page.click('button:has-text("Qayta generatsiya qilish")');

    await expect(page.getByText("Salom, DODA! (tahrirlangan)")).toBeVisible();
    // The original exchange must still be there, untouched — FR-CONV-007's
    // own acceptance criterion ("doesn't delete the old one").
    await expect(page.getByText("Salom, DODA!", { exact: true })).toBeVisible();

    const response = await page.request.get(
      `http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/conversations`,
      { headers: { Authorization: `Bearer ${SESSION_ID}` } },
    );
    const conversations = await response.json();
    const conversationId = conversations[0].id;
    const messagesResponse = await page.request.get(
      `http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/conversations/${conversationId}/messages`,
      { headers: { Authorization: `Bearer ${SESSION_ID}` } },
    );
    const messages: { role: string; content: string }[] = await messagesResponse.json();
    expect(messages.filter((m) => m.role === "USER")).toHaveLength(2);
  });

  await test.step("pinning a conversation provider persists server-side", async () => {
    // Scoped to the provider form specifically — the language form below
    // (FR-CONV-001) has its own, identically-labeled "Pin qilish" button,
    // and an unscoped click/text match would be exactly the strict-mode
    // ambiguity this codebase has already hit once before (see CLAUDE.md
    // on the AWAITING_APPROVAL/getByText lesson).
    const providerForm = page.locator('form:has(select[aria-label="Suhbat provayderi"])');
    await page.selectOption('select[aria-label="Suhbat provayderi"]', "GEMINI");
    await providerForm.getByRole("button", { name: "Pin qilish" }).click();
    await expect(providerForm.getByText("hozirgi: GEMINI")).toBeVisible();

    // Direct backend check (not the page's own fetch) — proves the pin
    // really persisted, not just that the label optimistically re-rendered.
    const response = await page.request.get(
      `http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/conversations`,
      { headers: { Authorization: `Bearer ${SESSION_ID}` } },
    );
    const conversations = await response.json();
    expect(conversations.some((c: { pinned_provider: string | null }) => c.pinned_provider === "GEMINI")).toBe(
      true,
    );
  });

  await test.step("pinning a conversation language persists server-side (FR-CONV-001)", async () => {
    const languageForm = page.locator('form:has(select[aria-label="Suhbat tili"])');
    await page.selectOption('select[aria-label="Suhbat tili"]', "RU");
    await languageForm.getByRole("button", { name: "Pin qilish" }).click();
    await expect(languageForm.getByText("hozirgi: RU")).toBeVisible();

    const response = await page.request.get(
      `http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/conversations`,
      { headers: { Authorization: `Bearer ${SESSION_ID}` } },
    );
    const conversations = await response.json();
    expect(
      conversations.some((c: { pinned_language: string | null }) => c.pinned_language === "RU"),
    ).toBe(true);

    await languageForm.getByRole("button", { name: "Avtomatikka qaytarish" }).click();
    await expect(languageForm.getByText("hozirgi: avtomatik aniqlash")).toBeVisible();
  });

  await test.step("setting the workspace's default language persists server-side (FR-WKS-007)", async () => {
    // Scoped to its own form — "Saqlash" is also the workspace AI
    // preference form's button text, the exact strict-mode collision
    // already documented above for the pin forms.
    const workspaceLanguageForm = page.locator('form:has(select[aria-label="Workspace standart tili"])');
    await page.selectOption('select[aria-label="Workspace standart tili"]', "RU");
    await workspaceLanguageForm.getByRole("button", { name: "Saqlash" }).click();
    await expect(workspaceLanguageForm.getByText("Workspace standart tili (RU):")).toBeVisible();

    // Direct backend check, not the page's own fetch — proves this is a
    // real, versioned/audited setting, not just an optimistic UI label.
    const response = await page.request.get(
      `http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/language-setting`,
      { headers: { Authorization: `Bearer ${SESSION_ID}` } },
    );
    expect(await response.json()).toEqual({ language: "RU" });

    const audit = await page.request.get(`http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/audit`, {
      headers: { Authorization: `Bearer ${SESSION_ID}` },
    });
    const events = await audit.json();
    expect(
      events.some((e: { event_type: string }) => e.event_type === "workspace.language_setting_changed.v1"),
    ).toBe(true);
  });

  await test.step("the earlier turn's cost shows up in the customer page's FinOps breakdown (NFR-COST-001)", async () => {
    // Direct backend check first — proves the aggregation itself, not just
    // that the page can render something.
    const report = await page.request.get(
      `http://localhost:8000/v1/customers/${CUSTOMER_ID}/ai-usage-report`,
      { headers: { Authorization: `Bearer ${SESSION_ID}` } },
    );
    const rows: { workspace_name: string; event_count: number }[] = await report.json();
    expect(rows.some((r) => r.workspace_name === "Demo Workspace" && r.event_count >= 1)).toBe(true);

    await page.goto(`/customers/${CUSTOMER_ID}`);
    await expect(page.getByRole("cell", { name: "Demo Workspace" })).toBeVisible();
  });

  expect(consoleErrors, `unexpected browser console errors: ${consoleErrors.join("\n")}`).toEqual([]);
});

test("chat: cancelling an in-flight turn resets the UI without an error", async ({ page }) => {
  // NullModelGateway (no real provider credential in this environment)
  // replies essentially instantly, far too fast to reliably click Cancel
  // before the turn finishes — so this test delays the browser's own
  // dispatch of the POST via page.route(), giving a deterministic window
  // to click "Bekor qilish" before the request even reaches the backend.
  // This proves the frontend's AbortController wiring and UI reset; the
  // backend's own claim (generation actually stops and the budget is
  // refunded) is proven server-side, with real interleaving, in
  // test_a_client_disconnect_mid_stream_stops_generation_and_refunds_the_reservation.
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  await page.goto("/login");
  await page.fill("#session-id", SESSION_ID);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/workspaces");
  await page.goto(`/workspaces/${WORKSPACE_ID}/chat`);
  await page.click('button:has-text("Yangi suhbat")');
  await expect(page.getByPlaceholder("Xabar yozing...")).toBeVisible();

  await page.route("**/conversations/*/messages", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    await route.continue();
  });

  await page.fill('input[placeholder="Xabar yozing..."]', "bu xabar bekor qilinadi");
  await page.click('button:has-text("Yuborish")');

  const cancelButton = page.getByRole("button", { name: "Bekor qilish" });
  await expect(cancelButton).toBeVisible();
  await cancelButton.click();

  // The UI returns to its idle state — composer re-enabled, no lingering
  // "sending" indicator, and (per handleSend's AbortError check) no error
  // message shown for what was the user's own deliberate cancellation.
  await expect(page.getByPlaceholder("Xabar yozing...")).toBeEnabled();
  await expect(cancelButton).not.toBeVisible();
  await expect(page.getByText("bekor qilinadi")).not.toBeVisible();

  expect(consoleErrors, `unexpected browser console errors: ${consoleErrors.join("\n")}`).toEqual([]);
});

test("chat: switching conversations mid-refresh never lets a stale response repaint the wrong one", async ({
  page,
}) => {
  // handleSend()'s finally block fires a listConversationMessages() GET for
  // the conversation the message was just sent in, but doesn't await it.
  // Network tracing (via page.on("request"/"response")) showed this GET is
  // NOT the first thing that happens after the reply text becomes visible —
  // NullModelGateway's reply renders via streamed/pending state well before
  // the stream actually ends and the finally block runs, so this GET can
  // fire even AFTER the user has already clicked "Yangi suhbat" to switch to
  // a brand-new conversation. If that switch happens first, the stale GET's
  // response (for the OLD conversation) must not overwrite the (correctly
  // empty) messages already showing for the new one.
  //
  // Because the stale GET's actual firing time floats relative to UI
  // events, this cannot be pinned down by delaying a route only up to some
  // visible checkpoint (an earlier version of this test did that, unrouting
  // right after the reply became visible, and it never observed the delayed
  // GET at all — the real one fired after unroute and went through
  // instantly, masking the race). Instead, the route delays only the FIRST
  // GET it ever sees for this test — that is always the send's own stale
  // refresh, since it is the first GET issued after the message is sent —
  // and lets every subsequent GET (the new conversation's own fetch) through
  // immediately, which is what actually isolates the race deterministically.
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  const needle = "sariq tulporli chumoli 77";

  await page.goto("/login");
  await page.fill("#session-id", SESSION_ID);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/workspaces");
  await page.goto(`/workspaces/${WORKSPACE_ID}/chat`);

  await page.click('button:has-text("Yangi suhbat")');
  await expect(page.getByPlaceholder("Xabar yozing...")).toBeVisible();

  let firstGetSeen = false;
  await page.route("**/conversations/*/messages", async (route) => {
    if (route.request().method() === "GET" && !firstGetSeen) {
      firstGetSeen = true;
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    await route.continue();
  });

  await page.fill('input[placeholder="Xabar yozing..."]', needle);
  await page.click('button:has-text("Yuborish")');
  await expect(page.getByText(needle, { exact: false }).first()).toBeVisible();

  // Switch to a second, brand-new conversation right away — the stale GET
  // (delayed above) has not resolved yet.
  await page.click('button:has-text("Yangi suhbat")');
  await expect(page.getByText(needle)).not.toBeVisible();

  // Wait past the artificial delay, so the stale GET's response has
  // definitely arrived by now — the assertion must still hold: it must not
  // have repainted conversation B with conversation A's messages.
  await page.waitForTimeout(2500);
  await expect(page.getByText(needle)).not.toBeVisible();

  await page.unroute("**/conversations/*/messages");
  expect(consoleErrors, `unexpected browser console errors: ${consoleErrors.join("\n")}`).toEqual([]);
});

test("chat: searching conversation history finds a message and jumps to its conversation", async ({
  page,
}) => {
  // FR-CONV-006. Uses a distinctive, unlikely-to-collide phrase (rather
  // than a generic word) so this test can't accidentally match content
  // left behind by another spec/run sharing the same seeded workspace.
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  const needle = "qizil sirli kalamush 42";

  await page.goto("/login");
  await page.fill("#session-id", SESSION_ID);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/workspaces");
  await page.goto(`/workspaces/${WORKSPACE_ID}/chat`);

  await page.click('button:has-text("Yangi suhbat")');
  await expect(page.getByPlaceholder("Xabar yozing...")).toBeVisible();
  await page.fill('input[placeholder="Xabar yozing..."]', needle);
  await page.click('button:has-text("Yuborish")');
  await expect(page.getByText(needle, { exact: false }).first()).toBeVisible();

  // Start a second, different conversation so there is more than one to
  // jump BETWEEN — proves the click actually navigates, not just that a
  // single already-open conversation happens to contain the text.
  await page.click('button:has-text("Yangi suhbat")');
  await expect(page.getByText(needle)).not.toBeVisible();

  await page.fill('input[placeholder="Suhbat tarixini qidirish..."]', needle);
  await page.click('button:has-text("Qidirish")');
  const resultButton = page.getByRole("button", { name: needle, exact: false });
  await expect(resultButton).toBeVisible();
  await resultButton.click();

  // Clicking a result clears the search panel and switches to the
  // conversation that actually contains the match.
  await expect(page.getByPlaceholder("Suhbat tarixini qidirish...")).toHaveValue("");
  await expect(page.getByText(needle, { exact: false }).first()).toBeVisible();

  await page.fill('input[placeholder="Suhbat tarixini qidirish..."]', "hech-qachon-mos-kelmaydigan-soz");
  await page.click('button:has-text("Qidirish")');
  await expect(page.getByText("Hech narsa topilmadi.")).toBeVisible();

  expect(consoleErrors, `unexpected browser console errors: ${consoleErrors.join("\n")}`).toEqual([]);
});

test("AI provider settings: enable/disable, test connection, fallback toggle, my preference", async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  await test.step("log in and open the customer page", async () => {
    await page.goto("/login");
    await page.fill("#session-id", SESSION_ID);
    await page.click('button[type="submit"]');
    await page.waitForURL("**/workspaces");
    await page.goto(`/customers/${CUSTOMER_ID}`);
    await expect(page.getByText("AI provayderlar")).toBeVisible();
  });

  await test.step("testing an unconfigured provider honestly reports failure, not a fake success", async () => {
    const openaiRow = page.locator("li", { hasText: "OPENAI" });
    await openaiRow.getByRole("button", { name: "Ulanishni tekshirish" }).click();
    await expect(openaiRow.getByText("tekshirilgan:")).toBeVisible();
  });

  await test.step("disabling and re-enabling a provider is real, not UI-only", async () => {
    const claudeRow = page.locator("li", { hasText: "CLAUDE" });
    await claudeRow.getByRole("button", { name: "O'chirish" }).click();
    await expect(claudeRow.getByRole("button", { name: "Yoqish" })).toBeVisible();

    const disabled = await page.request.get(`http://localhost:8000/v1/customers/${CUSTOMER_ID}/ai-providers`, {
      headers: { Authorization: `Bearer ${SESSION_ID}` },
    });
    const statuses = await disabled.json();
    expect(statuses.find((s: { provider: string; enabled: boolean }) => s.provider === "CLAUDE").enabled).toBe(
      false,
    );

    await claudeRow.getByRole("button", { name: "Yoqish" }).click();
    await expect(claudeRow.getByRole("button", { name: "O'chirish" })).toBeVisible();
  });

  await test.step("automatic fallback defaults to off and can be turned on", async () => {
    await expect(page.getByText("Avtomatik fallback")).toBeVisible();
    const fallbackRow = page.locator("div", { hasText: "Avtomatik fallback" }).first();
    await fallbackRow.getByRole("button", { name: "Yoqish" }).click();
    await expect(fallbackRow.getByRole("button", { name: "O'chirish" })).toBeVisible();

    const response = await page.request.get(`http://localhost:8000/v1/customers/${CUSTOMER_ID}/ai-fallback`, {
      headers: { Authorization: `Bearer ${SESSION_ID}` },
    });
    expect((await response.json()).enabled).toBe(true);
  });

  await test.step("setting my own AI preference round-trips through the real backend", async () => {
    await page.selectOption('select[aria-label="Mening AI provayderim"]', "CLAUDE");
    await page.click('form:has(select[aria-label="Mening AI provayderim"]) button:has-text("Saqlash")');
    await expect(page.getByText("Mening AI afzalligim (CLAUDE)")).toBeVisible();
  });

  expect(consoleErrors, `unexpected browser console errors: ${consoleErrors.join("\n")}`).toEqual([]);
});

test("chat: deleting a conversation removes it and cascades its messages (FR-KNW-007)", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  await page.goto("/login");
  await page.fill("#session-id", SESSION_ID);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/workspaces");
  await page.goto(`/workspaces/${WORKSPACE_ID}/chat`);

  const needle = "o'chiriladigan suhbat belgisi 99";
  await page.click('button:has-text("Yangi suhbat")');
  await expect(page.getByPlaceholder("Xabar yozing...")).toBeVisible();
  await page.fill('input[placeholder="Xabar yozing..."]', needle);
  await page.click('button:has-text("Yuborish")');
  await expect(page.getByText(needle, { exact: false }).first()).toBeVisible();

  // The conversation just created is prepended to the sidebar (newest
  // first), the same ordering GET .../conversations returns — so it is
  // both the sidebar's first <li> and this list's first element.
  const listBefore = await page.request.get(
    `http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/conversations`,
    { headers: { Authorization: `Bearer ${SESSION_ID}` } },
  );
  const conversationId = (await listBefore.json())[0].id;

  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("aside ul li").first().getByRole("button", { name: "Suhbatni o'chirish" }).click();

  // Deselected back to the empty state — its messages are gone from the
  // main panel too, not merely filtered out of the sidebar.
  await expect(page.getByText("Suhbat tanlang yoki yangisini yarating.")).toBeVisible();
  await expect(page.getByText(needle)).not.toBeVisible();

  // Direct backend check, not the page's own fetch — proves the delete is
  // real and its Message children actually cascade (migration 0031), not
  // just a UI-side filter.
  const messagesAfter = await page.request.get(
    `http://localhost:8000/v1/workspaces/${WORKSPACE_ID}/conversations/${conversationId}/messages`,
    { headers: { Authorization: `Bearer ${SESSION_ID}` } },
  );
  expect(messagesAfter.status()).toBe(404);

  expect(consoleErrors, `unexpected browser console errors: ${consoleErrors.join("\n")}`).toEqual([]);
});
