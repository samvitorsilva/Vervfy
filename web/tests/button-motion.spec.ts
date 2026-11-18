import { expect, test } from "@playwright/test";

test("buttons ease into and out of the pressed state", async ({ page }) => {
  await page.goto("/login");
  const button = page.locator(".auth-submit");
  await expect(button).toBeVisible();
  await button.evaluate((element) => { element.removeAttribute("disabled"); });
  const before = await button.evaluate((element) => getComputedStyle(element).transitionProperty);
  expect(before.split(", ")).toContain("scale");
  await button.hover();
  await page.mouse.down();
  await expect.poll(() => button.evaluate((element) => getComputedStyle(element).scale)).toBe("0.97");
  await page.mouse.up();
  await expect.poll(() => button.evaluate((element) => getComputedStyle(element).scale)).toBe("none");
});
