import { apiFetch, expectOk } from "@/lib/api/client";

export type PasskeyAction =
  | "password_add"
  | "email_change"
  | "logout_all"
  | "recovery_rotate";

export interface PasskeyProof {
  passkey_intent_id: string;
  passkey_proof_id: string;
}

export interface PasskeySecurityStatus {
  has_password: boolean;
  google_linked: boolean;
  passkey_count: number;
  recovery_codes_remaining: number;
}

export interface PasskeyEnrollmentEligibility {
  eligible: boolean;
  reason: string | null;
  passkey_count: number;
}

interface ApiPayload {
  [key: string]: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function decodeBase64Url(value: unknown): ArrayBuffer {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new Error("The passkey service returned invalid credential options.");
  }
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

function encodeBase64Url(value: ArrayBuffer): string {
  const bytes = new Uint8Array(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function jsonCredentialDescriptor(value: unknown): PublicKeyCredentialDescriptor {
  if (!isRecord(value) || typeof value.id !== "string") {
    throw new Error("The passkey service returned invalid credential options.");
  }
  const descriptor: PublicKeyCredentialDescriptor = {
    id: decodeBase64Url(value.id),
    type: "public-key",
  };
  if (Array.isArray(value.transports)) {
    descriptor.transports = value.transports.filter(
      (transport): transport is AuthenticatorTransport =>
        transport === "ble" ||
        transport === "hybrid" ||
        transport === "internal" ||
        transport === "nfc" ||
        transport === "usb",
    );
  }
  return descriptor;
}

function creationOptions(value: unknown): PublicKeyCredentialCreationOptions {
  if (
    !isRecord(value) ||
    !isRecord(value.rp) ||
    typeof value.rp.name !== "string" ||
    !isRecord(value.user) ||
    typeof value.user.name !== "string" ||
    typeof value.user.displayName !== "string" ||
    !Array.isArray(value.pubKeyCredParams)
  ) {
    throw new Error("The passkey service returned invalid registration options.");
  }
  const options: PublicKeyCredentialCreationOptions = {
    challenge: decodeBase64Url(value.challenge),
    rp: {
      name: value.rp.name,
      ...(typeof value.rp.id === "string" ? { id: value.rp.id } : {}),
    },
    user: {
      id: decodeBase64Url(value.user.id),
      name: value.user.name,
      displayName: value.user.displayName,
    },
    pubKeyCredParams: value.pubKeyCredParams.filter(
      (parameter): parameter is PublicKeyCredentialParameters =>
        isRecord(parameter) &&
        parameter.type === "public-key" &&
        typeof parameter.alg === "number",
    ),
  };
  if (typeof value.timeout === "number") options.timeout = value.timeout;
  if (Array.isArray(value.excludeCredentials)) {
    options.excludeCredentials = value.excludeCredentials.map(jsonCredentialDescriptor);
  }
  if (isRecord(value.authenticatorSelection)) {
    const selection: AuthenticatorSelectionCriteria = {};
    if (
      value.authenticatorSelection.authenticatorAttachment === "platform" ||
      value.authenticatorSelection.authenticatorAttachment === "cross-platform"
    ) {
      selection.authenticatorAttachment =
        value.authenticatorSelection.authenticatorAttachment;
    }
    if (
      value.authenticatorSelection.residentKey === "required" ||
      value.authenticatorSelection.residentKey === "preferred" ||
      value.authenticatorSelection.residentKey === "discouraged"
    ) {
      selection.residentKey = value.authenticatorSelection.residentKey;
    }
    if (typeof value.authenticatorSelection.requireResidentKey === "boolean") {
      selection.requireResidentKey =
        value.authenticatorSelection.requireResidentKey;
    }
    if (
      value.authenticatorSelection.userVerification === "required" ||
      value.authenticatorSelection.userVerification === "preferred" ||
      value.authenticatorSelection.userVerification === "discouraged"
    ) {
      selection.userVerification = value.authenticatorSelection.userVerification;
    }
    options.authenticatorSelection = selection;
  }
  if (value.attestation === "none" || value.attestation === "direct" || value.attestation === "indirect" || value.attestation === "enterprise") {
    options.attestation = value.attestation;
  }
  return options;
}

function requestOptions(value: unknown): PublicKeyCredentialRequestOptions {
  if (!isRecord(value) || typeof value.rpId !== "string") {
    throw new Error("The passkey service returned invalid verification options.");
  }
  const options: PublicKeyCredentialRequestOptions = {
    challenge: decodeBase64Url(value.challenge),
    rpId: value.rpId,
    userVerification: "required",
  };
  if (typeof value.timeout === "number") options.timeout = value.timeout;
  if (Array.isArray(value.allowCredentials)) {
    options.allowCredentials = value.allowCredentials.map(jsonCredentialDescriptor);
  }
  return options;
}

function serializeCredential(credential: PublicKeyCredential): ApiPayload {
  const response = credential.response;
  const responseData: ApiPayload = {
    clientDataJSON: encodeBase64Url(response.clientDataJSON),
  };
  if (response instanceof AuthenticatorAttestationResponse) {
    responseData.attestationObject = encodeBase64Url(response.attestationObject);
  } else if (response instanceof AuthenticatorAssertionResponse) {
    responseData.authenticatorData = encodeBase64Url(response.authenticatorData);
    responseData.signature = encodeBase64Url(response.signature);
    responseData.userHandle = response.userHandle
      ? encodeBase64Url(response.userHandle)
      : null;
  } else {
    throw new Error("The browser returned an unsupported passkey response.");
  }
  return {
    id: credential.id,
    rawId: encodeBase64Url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    response: responseData,
  };
}

function requireBrowserSupport(): void {
  if (
    typeof window === "undefined" ||
    !window.isSecureContext ||
    typeof PublicKeyCredential === "undefined" ||
    typeof navigator.credentials?.create !== "function" ||
    typeof navigator.credentials?.get !== "function"
  ) {
    throw new Error("Passkeys are not supported in this browser or connection.");
  }
}

async function postJson<T>(path: string, payload: ApiPayload): Promise<T> {
  const response = await apiFetch(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    { csrf: true, retryCsrfOnForbidden: true },
  );
  await expectOk(response);
  return response.json() as Promise<T>;
}

async function createAssertion(action: PasskeyAction, payload: ApiPayload) {
  const intent = await postJson<{ intent_id: string }>(
    "/api/account/passkeys/action-intents",
    { action, ...payload },
  );
  const ceremony = await postJson<{
    challenge_id: string;
    options: unknown;
  }>(`/api/account/passkeys/actions/${action}/options`, {
    intent_id: intent.intent_id,
  });
  requireBrowserSupport();
  const credential = await navigator.credentials.get({
    publicKey: requestOptions(ceremony.options),
  });
  if (!(credential instanceof PublicKeyCredential)) {
    throw new Error("The browser did not return a passkey.");
  }
  const result = await postJson<{ proof_id: string }>(
    `/api/account/passkeys/actions/${action}/complete`,
    {
      intent_id: intent.intent_id,
      challenge_id: ceremony.challenge_id,
      response: serializeCredential(credential),
    },
  );
  return {
    passkey_intent_id: intent.intent_id,
    passkey_proof_id: result.proof_id,
  };
}

export function isPasskeyBrowserSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    window.isSecureContext &&
    typeof PublicKeyCredential !== "undefined" &&
    typeof navigator.credentials?.create === "function" &&
    typeof navigator.credentials?.get === "function"
  );
}

export async function registerPasskey(currentPassword: string): Promise<void> {
  requireBrowserSupport();
  const authorization = await postJson<{ authorization_id: string }>(
    "/api/account/passkeys/registration/authorize",
    { current_password: currentPassword },
  );
  const ceremony = await postJson<{
    challenge_id: string;
    options: unknown;
  }>("/api/account/passkeys/registration/options", {
    authorization_id: authorization.authorization_id,
  });
  const credential = await navigator.credentials.create({
    publicKey: creationOptions(ceremony.options),
  });
  if (!(credential instanceof PublicKeyCredential)) {
    throw new Error("The browser did not create a passkey.");
  }
  await postJson("/api/account/passkeys/registration/complete", {
    authorization_id: authorization.authorization_id,
    challenge_id: ceremony.challenge_id,
    response: serializeCredential(credential),
  });
}

export function verifyPasskeyAction(
  action: Exclude<PasskeyAction, "recovery_rotate">,
  payload: ApiPayload = {},
): Promise<PasskeyProof> {
  requireBrowserSupport();
  return createAssertion(action, payload);
}

export async function issueRecoveryCodes(): Promise<string[]> {
  requireBrowserSupport();
  const proof = await createAssertion("recovery_rotate", {});
  const result = await postJson<{ recovery_codes: string[] }>(
    "/api/account/passkeys/recovery/codes",
    {
      intent_id: proof.passkey_intent_id,
      proof_id: proof.passkey_proof_id,
    },
  );
  return result.recovery_codes;
}

export async function loadPasskeySecurity(): Promise<{
  methods: PasskeySecurityStatus;
  enrollment: PasskeyEnrollmentEligibility;
}> {
  const fetchStatus = async <T,>(path: string): Promise<T> => {
    const response = await apiFetch(
      path,
      {},
      { csrf: true, retryCsrfOnForbidden: true },
    );
    await expectOk(response);
    return response.json() as Promise<T>;
  };
  const methods = await fetchStatus<PasskeySecurityStatus>(
    "/api/account/security-methods",
  );
  const enrollment = await fetchStatus<PasskeyEnrollmentEligibility>(
    "/api/account/passkeys/enrollment-eligibility",
  );
  return { methods, enrollment };
}
