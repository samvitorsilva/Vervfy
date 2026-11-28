import { expect, test } from "@playwright/test";

test("authentication buttons ease into and out of the pressed state", async ({ page }) => {
  await page.goto("/login");
  const button = page.locator(".auth-submit");
  await expect(button).toBeVisible();
  await button.evaluate((element) => { element.removeAttribute("disabled"); });
  const before = await button.evaluate((element) => getComputedStyle(element).transitionProperty);
  expect(before.split(", ")).toContain("filter");
  await button.hover();
  await page.mouse.down();
  await expect.poll(() => button.evaluate((element) => getComputedStyle(element).filter)).toBe("brightness(0.9)");
  await page.mouse.up();
  await page.mouse.move(0, 0);
  await expect.poll(() => button.evaluate((element) => getComputedStyle(element).filter)).toBe("none");
});
