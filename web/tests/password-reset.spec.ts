import { expect, test, type Page } from "@playwright/test";

async function loadRecoveryPage(page: Page, fragment: string) {
  await page.addInitScript(() => {
    const observer = new MutationObserver(() => {
      if (!document.body) return;
      observer.disconnect();
      const analyticsScript = document.createElement("script");
      analyticsScript.nonce =
        document.querySelector<HTMLScriptElement>("script[nonce]")?.nonce ?? "";
      analyticsScript.textContent =
        "window.__analyticsObservedRecoveryHash = location.hash;";
      document.body.prepend(analyticsScript);
    });
    observer.observe(document, { childList: true, subtree: true });
  });
  const response = await page.goto(`/reset-password${fragment}`);
  const html = await response?.text();
  const bootstrapIndex = html?.indexOf("recoveryValues") ?? -1;
  const bodyIndex = html?.indexOf("<body") ?? -1;
  expect(bootstrapIndex).toBeGreaterThanOrEqual(0);
  expect(bootstrapIndex).toBeLessThan(bodyIndex);
  const observedHash = await page.evaluate(
    () =>
      (window as Window & { __analyticsObservedRecoveryHash?: string })
        .__analyticsObservedRecoveryHash,
  );
  expect(observedHash).toBe("");
  return response;
}

test("forgot-password and reset screens complete the synthetic flow", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await page.getByLabel("Email").fill("synthetic@example.test");
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByRole("status")).toContainText(
    "If an account exists for that email",
  );

  const resetResponse = await loadRecoveryPage(
    page,
    "#token=synthetic-reset-token",
  );
  expect(resetResponse?.headers()["referrer-policy"]).toBe("no-referrer");
  await expect(page).toHaveURL(/\/reset-password$/);
  await expect(page.getByLabel("New password", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/reset-password$/);
  await expect(page.locator('meta[name="referrer"]')).toHaveAttribute(
    "content",
    "no-referrer",
  );
  const hasThirdPartyScript = await page.locator("script[src]").evaluateAll((scripts) =>
    scripts.some((script) => new URL((script as HTMLScriptElement).src).origin !== location.origin),
  );
  expect(hasThirdPartyScript).toBe(false);

  await page
    .getByLabel("New password", { exact: true })
    .fill("synthetic-password-123");
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("synthetic-password-123");
  await page.getByRole("button", { name: "Reset password" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Your password has been updated",
  );
});

test("unverified account email link is cleaned and verified without exposing its token", async ({
  page,
}) => {
  await loadRecoveryPage(
    page,
    "#verify=synthetic-verification-token",
  );
  await page.getByRole("button", { name: "Verify email and continue" }).click();
  await expect(page.getByRole("status")).toContainText(
    "If you own this email address",
  );
  await expect(page).toHaveURL(/\/reset-password$/);
});
