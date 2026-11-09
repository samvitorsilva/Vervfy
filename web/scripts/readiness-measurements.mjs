// Local production-build lab measurements; no real users or field telemetry.
import { chromium } from "@playwright/test";
import { writeFile } from "node:fs/promises";

const origin = process.env.AUDIT_BASE_URL ?? "http://127.0.0.1:3102";
if (new URL(origin).hostname !== "127.0.0.1") throw new Error("Local audit only");
const browser = await chromium.launch();
const results = [];
try {
  for (const viewport of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
    for (let sample = 0; sample < 3; sample++) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      await page.addInitScript(() => {
        window.auditVitals = { lcp: null, shifts: [], events: [] };
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) window.auditVitals.lcp = entry.startTime;
        }).observe({ type: "largest-contentful-paint", buffered: true });
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!entry.hadRecentInput) window.auditVitals.shifts.push({ time: entry.startTime, value: entry.value });
          }
        }).observe({ type: "layout-shift", buffered: true });
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.interactionId) window.auditVitals.events.push(entry.duration);
          }
        }).observe({ type: "event", buffered: true, durationThreshold: 16 });
      });
      await page.goto(`${origin}/login`);
      await page.getByRole("button", { name: "Log in", exact: true }).waitFor();
      await page.waitForTimeout(1500);
      await page.locator("#username").pressSequentially("audit", { delay: 50 });
      await page.locator("#password").click();
      await page.waitForTimeout(250);
      const measurements = await page.evaluate(() => {
        const nav = performance.getEntriesByType("navigation")[0];
        let cls = 0, session = 0, start = 0, last = 0;
        for (const shift of window.auditVitals.shifts) {
          if (shift.time - last > 1000 || shift.time - start > 5000) { session = 0; start = shift.time; }
          session += shift.value; cls = Math.max(cls, session); last = shift.time;
        }
        const parse = (color) => color.match(/[\d.]+/g).map(Number);
        const blend = (fg, bg) => fg.slice(0, 3).map((v, i) => v * (fg[3] ?? 1) + bg[i] * (1 - (fg[3] ?? 1)));
        const luminance = (rgb) => rgb.map((v) => v / 255).map((v) => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
        const ratio = (a, b) => (Math.max(luminance(a), luminance(b)) + .05) / (Math.min(luminance(a), luminance(b)) + .05);
        const background = (element) => {
          const chain = [];
          for (let node = element; node; node = node.parentElement) chain.unshift(node);
          return chain.reduce((rgb, node) => blend(parse(getComputedStyle(node).backgroundColor), rgb), [0, 0, 0]);
        };
        const contrast = [".auth-title", ".auth-sub", ".auth-field label", ".auth-password-hint", ".auth-footer", ".site-footer a"].map((selector) => {
          const element = document.querySelector(selector);
          const bg = background(element);
          return { selector, ratio: +ratio(blend(parse(getComputedStyle(element).color), bg), bg).toFixed(2) };
        });
        const input = document.querySelector("#username");
        const inputBg = background(input);
        const border = blend(parse(getComputedStyle(input).borderTopColor), inputBg);
        const fields = { borderAgainstInput: +ratio(border, inputBg).toFixed(2), borderAgainstCard: +ratio(border, background(input.parentElement)).toFixed(2) };
        return {
          ttfbMs: +(nav.responseStart - nav.requestStart).toFixed(1),
          lcpMs: window.auditVitals.lcp,
          cls: +cls.toFixed(5),
          maxObservedInteractionMs: window.auditVitals.events.length ? Math.max(...window.auditVitals.events) : null,
          transferredBytes: performance.getEntriesByType("resource").reduce((sum, entry) => sum + entry.transferSize, nav.transferSize),
          contrast, fields,
        };
      });
      results.push({ viewport, sample: sample + 1, ...measurements });
      if (sample === 0) await page.screenshot({ path: `/tmp/vervfy-audit-${viewport.width}.png`, fullPage: true });
      await context.close();
    }
  }
} finally { await browser.close(); }
await writeFile("/tmp/vervfy-readiness-measurements.json", JSON.stringify(results, null, 2));
console.log(JSON.stringify(results, null, 2));
