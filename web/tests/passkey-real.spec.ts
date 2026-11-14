import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import path from 'node:path';

const origin = 'https://vervfy.test';
const actionPath = '/api/account/passkeys/actions/email_change';

// Runs before the page/browser fixtures. Missing permissions or dependencies fail,
// never skip. No user-supplied URL, executable, profile, or storage state is used.
test.beforeAll(({}, testInfo) => {
  test.skip(testInfo.project.metadata.realPasskey !== true, 'Requires the dedicated real-passkey configuration');
  if (process.env.VERVFY_RUN_REAL_PASSKEY_E2E !== '1') {
    throw new Error('Real E2E requires explicit VERVFY_RUN_REAL_PASSKEY_E2E=1 authorization');
  }
  execFileSync(path.resolve('../.venv/bin/python'), [path.resolve('tests/passkey-real-preflight.py')], {
    cwd: process.cwd(), stdio: 'pipe', timeout: 30_000,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
});

async function api(page: Page, method: string, endpoint: string, body?: unknown) {
  return page.evaluate(async ({ method, endpoint, body }) => {
    const csrfResponse = await fetch('/api/csrf', { redirect: 'error', cache: 'no-store' });
    if (!csrfResponse.ok) throw new Error(`CSRF acquisition failed: ${csrfResponse.status}`);
    const csrf = await csrfResponse.json();
    const response = await fetch(endpoint, {
      method, redirect: 'error', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf.csrf_token },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    return { status: response.status, body: await response.json() };
  }, { method, endpoint, body });
}

async function state(page: Page) {
  const me = await api(page, 'GET', '/api/me');
  const security = await api(page, 'GET', '/api/account/security-methods');
  expect(me.status).toBe(200);
  expect(security.status).toBe(200);
  return { me: me.body, security: security.body };
}

async function assertion(page: Page, email: string) {
  const intent = await api(page, 'POST', '/api/account/passkeys/action-intents', { action: 'email_change', email });
  expect(intent.status).toBe(200);
  const ceremony = await api(page, 'POST', `${actionPath}/options`, { intent_id: intent.body.intent_id });
  expect(ceremony.status).toBe(200);
  expect(ceremony.body.options.rpId).toBe('vervfy.test');
  expect(ceremony.body.options.userVerification).toBe('required');
  const response = await page.evaluate(async (options) => {
    const decode = (value: string) => Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
    const encode = (value: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const credential = await navigator.credentials.get({ publicKey: {
      ...options, challenge: decode(options.challenge),
      allowCredentials: options.allowCredentials?.map((c: { id: string }) => ({ ...c, id: decode(c.id) })),
    } }) as PublicKeyCredential;
    if (!credential) throw new Error('Authenticator returned no credential');
    const result = credential.response as AuthenticatorAssertionResponse;
    return { id: credential.id, rawId: encode(credential.rawId), type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment,
      response: { clientDataJSON: encode(result.clientDataJSON), authenticatorData: encode(result.authenticatorData), signature: encode(result.signature), userHandle: result.userHandle ? encode(result.userHandle) : null } };
  }, ceremony.body.options);
  return { intent_id: intent.body.intent_id, challenge_id: ceremony.body.challenge_id, response };
}

test('isolated HTTPS registration, enrollment, reauthentication and replay rejection', async ({ page, context, browserName }) => {
  expect(browserName).toBe('chromium');
  const unexpected: string[] = [];
  await context.route('**/*', async route => {
    if (new URL(route.request().url()).origin !== origin) {
      unexpected.push(new URL(route.request().url()).origin);
      await route.abort('blockedbyclient');
    } else await route.continue();
  });
  // Playwright's normal launch creates a disposable temporary profile; no channel,
  // executablePath, persistent context, or user's profile is supplied.
  await page.goto(`${origin}/register`);
  expect(await page.evaluate(() => window.isSecureContext)).toBe(true);
  expect(new URL(page.url()).origin).toBe(origin);
  const config = await api(page, 'GET', '/api/config');
  expect(config.status).toBe(200);
  expect(config.body.google_oauth_enabled).toBe(false);
  const cdp = await context.newCDPSession(page);
  await cdp.send('WebAuthn.enable');
  const { authenticatorId } = await cdp.send('WebAuthn.addVirtualAuthenticator', { options: {
    protocol: 'ctap2', transport: 'internal', hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true,
  } });
  try {
    const suffix = randomBytes(8).toString('hex');
    const password = randomBytes(24).toString('base64url');
    await page.getByLabel('Username', { exact: true }).fill(`pk_${suffix}`);
    await page.getByLabel('Email (optional, not used to sign in)', { exact: true }).fill(`pk-${suffix}@example.test`);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Create account', exact: true }).click();
    await expect(page).toHaveURL(`${origin}/`);
    const initial = await state(page);
    expect(initial.security.passkey_count).toBe(0);
    await page.getByRole('button', { name: 'Open account' }).click();
    await page.getByLabel('Current password').last().fill(password);
    const registrationOptions = page.waitForResponse(r => new URL(r.url()).pathname === '/api/account/passkeys/registration/options');
    await page.getByRole('button', { name: 'Add a passkey' }).click();
    const optionsResponse = await registrationOptions;
    expect(optionsResponse.status()).toBe(200);
    expect((await optionsResponse.json()).options.rp.id).toBe('vervfy.test');
    await expect(page.getByRole('status').filter({ hasText: 'Passkey added.' })).toBeVisible();
    expect((await state(page)).security.passkey_count).toBe(1);
    const credentials = await cdp.send('WebAuthn.getCredentials', { authenticatorId });
    expect(credentials.credentials).toHaveLength(1);
    expect(credentials.credentials[0]).toMatchObject({ rpId: 'vervfy.test', isResidentCredential: true });

    // Genuine browser signature, corrupted before its FIRST submission.
    const bad = await assertion(page, `invalid-${suffix}@example.test`);
    const signature = Buffer.from(bad.response.response.signature, 'base64url');
    signature[signature.length - 1] ^= 1;
    bad.response.response.signature = signature.toString('base64url');
    const beforeBad = await state(page);
    const rejected = await api(page, 'POST', `${actionPath}/complete`, bad);
    expect(rejected).toEqual({ status: 400, body: { detail: 'Passkey request could not be completed' } });
    expect(await state(page)).toEqual(beforeBad);

    // Fresh challenge after the rejected ceremony; never reuse a burned challenge.
    const email = `changed-${suffix}@example.test`;
    const good = await assertion(page, email);
    const completed = await api(page, 'POST', `${actionPath}/complete`, good);
    expect(completed.status).toBe(200);
    expect(completed.body.proof_id).toMatch(/^[A-Za-z0-9_-]{43}$/);
    const beforeReplay = await state(page);
    expect(await api(page, 'POST', `${actionPath}/complete`, good)).toEqual({ status: 400, body: { detail: 'Passkey request could not be completed' } });
    expect(await state(page)).toEqual(beforeReplay);
    const mutation = { email, passkey_intent_id: good.intent_id, passkey_proof_id: completed.body.proof_id };
    expect((await api(page, 'PUT', '/api/account/email', mutation)).status).toBe(200);
    const afterChange = await state(page);
    expect(afterChange.me.email).toBe(email);
    expect(await api(page, 'PUT', '/api/account/email', mutation)).toEqual({ status: 403, body: { detail: 'Passkey proof is invalid or expired' } });
    expect(await state(page)).toEqual(afterChange);
    expect(unexpected).toEqual([]);
  } finally {
    await cdp.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId });
    await cdp.detach();
  }
});
