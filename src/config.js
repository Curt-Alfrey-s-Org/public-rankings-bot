function getApiBaseUrl() {
  const fromEnv = typeof process !== 'undefined' && (process.env.API_URL || process.env.EXPO_PUBLIC_API_URL);
  if (fromEnv) {
    return String(fromEnv).replace(/\/$/, '');
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return 'https://www.probilliardssoftware.com';
}

export const API_BASE_URL = getApiBaseUrl();