import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const source = await readFile(new URL("../src/components/app-loading-skeleton.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext } }).outputText;
const code = compiled.replaceAll('"react/jsx-runtime"', JSON.stringify(pathToFileURL(require.resolve("react/jsx-runtime")).href));
const { default: Skeleton } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
const render = (view, listMode = "grid", compact = false) => renderToStaticMarkup(createElement(Skeleton, { view, listMode, compact, label: "Loading content" }));

test("loading layouts match each destination and track display mode", () => {
  for (const view of ["library", "favorites", "offline", "playlist:example", "artist:Example"]) {
    assert.match(render(view), /app-skeleton-track-grid/);
    const list = render(view, "list");
    assert.match(list, /app-skeleton-track-list/);
    assert.doesNotMatch(list, /app-skeleton-track-grid/);
  }
  for (const [view, expected] of [["artists", "app-skeleton-artists"], ["playlists", "app-skeleton-playlists"], ["account", "app-skeleton-account"], ["recap", "app-skeleton-recap"]]) {
    const html = render(view);
    assert.match(html, new RegExp(expected));
    assert.doesNotMatch(html, /app-skeleton-track-grid/);
    assert.match(html, /aria-busy="true"/);
    assert.doesNotMatch(html, /<button|<input|<a\s/);
  }
});

test("account reserves its settings sections and recap uses tracks instead of charts", () => {
  const account = render("account");
  assert.equal((account.match(/acct-settings-group/g) ?? []).length, 4);
  assert.match(account, /acct-danger-zone/);
  assert.equal((render("recap").match(/recap-period app-skeleton-recap-card/g) ?? []).length, 2);
  assert.doesNotMatch(render("recap"), /app-skeleton-recap-chart/);
  assert.match(render("recap"), /app-skeleton-recap-track/);
  assert.doesNotMatch(render("recap", "grid", true), /recap-overview/);
});
