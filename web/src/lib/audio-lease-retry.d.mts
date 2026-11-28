export function requestWithBoundedRetries(
  request: (signal: AbortSignal) => Promise<Response>,
  wait: (milliseconds: number, signal: AbortSignal) => Promise<void>,
  signal: AbortSignal,
): Promise<Response>;
