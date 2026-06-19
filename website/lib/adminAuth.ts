/**
 * Gedeelde auth-constanten voor de admin-sectie.
 * Dit bestand is importeerbaar vanuit zowel server components als route handlers.
 * NOOIT importeren in client components.
 */
export const SESSION_COOKIE = "admin_session";
export const COOKIE_MAX_AGE = 60 * 60 * 8; // 8 uur
