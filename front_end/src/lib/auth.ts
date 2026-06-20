/**
 * Token storage helpers.
 *
 * We keep tokens in localStorage so a page refresh keeps the user logged in,
 * but each call to apiGet/apiPost always re-reads the current value from
 * the auth store so logout takes effect immediately.
 */
const ACCESS_KEY = "sgd.access_token";
const REFRESH_KEY = "sgd.refresh_token";

export const readAccessToken = (): string | null => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
};

export const readRefreshToken = (): string | null => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
};

export const writeTokens = (access: string, refresh: string): void => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
};

export const clearTokens = (): void => {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
};
