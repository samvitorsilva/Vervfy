import { expect, test, type Page } from "@playwright/test";

async function openDeletion(page: Page, baseURL: string) {
  await page.route(/^https:\/\//, route => route.abort());
  const origin = new URL(baseURL).origin;
  await page.context().addCookies([
    { name: "vervfy_playwright_session", value: "authenticated", url: origin },
    { name: "auralis_session", value: "test-ui-hint", url: origin },
  ]);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open account", exact: true }).click();
  await page.getByRole("button", { name: "Delete account", exact: true }).click();
}

async function hold(page: Page) {
  const button = page.locator(".acct-delete-hold");
  await button.focus();
  await page.keyboard.down("Space");
  await expect(button).toHaveAttribute("data-holding", "true");
  await expect(button).not.toHaveAttribute("data-holding", "true");
  await page.keyboard.up("Space");
}

for (const reducedMotion of ["no-preference", "reduce"] as const) {
  test(`moving between account sections does not replay entrance animations (${reducedMotion})`, async ({ page, baseURL }) => {
    await page.emulateMedia({ reducedMotion });
    // Keep the deletion flow unopened until the initial account entrance finishes.
    await page.route(/^https:\/\//, route => route.abort());
    const origin = new URL(baseURL!).origin;
    await page.context().addCookies([
      { name: "vervfy_playwright_session", value: "authenticated", url: origin },
      { name: "auralis_session", value: "test-ui-hint", url: origin },
    ]);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Open account", exact: true }).click();
    const account = page.locator(".account-view:not(.app-skeleton-account)");
    const deletion = account.locator(".acct-danger-zone");
    await expect(deletion).toBeVisible();
    await expect.poll(() => account.evaluate(element => element.getAnimations({ subtree: true })
      .filter(animation => animation instanceof CSSAnimation && animation.animationName === "loadedContentEnter" && animation.playState === "running").length)).toBe(0);
    await account.evaluate(element => {
      element.setAttribute("data-entrance-restarts", "0");
      element.addEventListener("animationstart", event => {
        if ((event as AnimationEvent).animationName === "loadedContentEnter") {
          element.setAttribute("data-entrance-restarts", String(Number(element.getAttribute("data-entrance-restarts")) + 1));
        }
      });
    });
    const animationName = reducedMotion === "reduce" ? "none" : "loadedContentEnter";
    await page.getByRole("button", { name: "Delete account", exact: true }).click();
    await expect(deletion).toHaveCSS("opacity", "1");
    await expect(deletion).toHaveCSS("animation-name", animationName);
    await page.getByRole("heading", { name: "Session", exact: true }).click();
    // Also exercise keyboard focus moving out of and back into the section.
    await page.getByLabel("Current password", { exact: true }).focus();
    await expect(deletion).toHaveCSS("opacity", "1");
    await expect(deletion).toHaveCSS("animation-name", animationName);
    await account.locator(".acct-session button").first().focus();
    await expect.poll(() => deletion.evaluate(element => element.matches(":focus-within"))).toBe(false);
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(account).toHaveAttribute("data-entrance-restarts", "0");
    await expect(deletion).toHaveCSS("opacity", "1");
  });
}

test("deletion requires valid proof and a full hold, and failed requests can be retried", async ({ page, baseURL }) => {
  let requests = 0;
  let release: (() => void) | undefined;
  await page.route("**/api/account", async route => {
    requests++;
    expect(route.request().method()).toBe("DELETE");
    expect(route.request().postDataJSON()).toEqual({ current_password: "wrong-password", confirmation: "DELETE" });
    await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({ status: 400, json: { detail: "Incorrect password" } });
  });
  await openDeletion(page, baseURL!);
  const button = page.locator(".acct-delete-hold");
  await hold(page);
  await expect(button).toHaveText("Hold to delete account");
  expect(requests).toBe(0);
  await page.getByLabel("Current password", { exact: true }).fill("wrong-password");
  await page.getByLabel("Type DELETE to confirm").fill("delete");
  await hold(page);
  expect(requests).toBe(0);
  await page.getByLabel("Type DELETE to confirm").fill("DELETE");
  await button.click();
  expect(requests).toBe(0);
  await hold(page);
  await expect(button).toHaveText("Deleting account…");
  await expect(button).toBeDisabled();
  await expect(button).not.toHaveAttribute("data-complete", "true");
  expect(requests).toBe(1);
  release?.();
  await expect(page.getByRole("status").filter({ hasText: "Incorrect password" })).toBeVisible();
  await expect(button).toBeEnabled();
  await expect(button).toHaveText("Hold to delete account");
  await hold(page);
  expect(requests).toBe(2);
  release?.();
  await expect(button).toBeEnabled();
});
