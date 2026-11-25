// The official SDK sends JSON strings with fetch. Limit retry to this route.
import { setTimeout as sleep } from 'node:timers/promises';
const originalFetch = globalThis.fetch.bind(globalThis);
const endpoint = process.env.MATRIX_ENDPOINT || 'https://api.deepseek.com/chat/completions';
const statuses = new Set([429, 500, 502, 503, 504]);
globalThis.fetch = async (input, options) => {
  const url = input instanceof Request ? input.url : String(input);
  if (url !== endpoint || options?.method?.toUpperCase() !== 'POST' ||
      typeof options.body !== 'string') return originalFetch(input, options);
  for (let retry = 0; ; retry++) {
    const response = await originalFetch(input, options);
    if (retry >= 2 || !statuses.has(response.status)) return response;
    const header = response.headers.get('retry-after');
    const seconds = Number(header);
    const requested = Number.isNaN(seconds) ? (Date.parse(header) - Date.now()) / 1000 : seconds;
    const delay = Math.max(2 ** retry + Math.random() * 0.25, requested || 0);
    if (delay > 30) return response;
    await response.body?.cancel();
    await sleep(delay * 1000, undefined, { signal: options.signal });
  }
};
