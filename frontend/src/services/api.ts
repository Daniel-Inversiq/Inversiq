const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api';

function getApiBaseUrl(): string {
  const envBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (typeof envBaseUrl === 'string' && envBaseUrl.trim().length > 0) {
    return envBaseUrl.replace(/\/+$/, '');
  }
  return DEFAULT_API_BASE_URL;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly details: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const response = await fetch(`${baseUrl}${normalizedPath}`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  const contentType = response.headers.get('content-type') ?? '';
  const isJson = contentType.includes('application/json');
  const payload: unknown = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    if (isJson && typeof payload === 'object' && payload !== null && 'detail' in payload) {
      const detail = (payload as { detail?: unknown }).detail;
      if (typeof detail === 'string' && detail.trim().length > 0) {
        message = detail;
      }
    } else if (typeof payload === 'string' && payload.trim().length > 0) {
      message = payload;
    }
    throw new ApiError(message, response.status, payload);
  }

  if (!isJson) {
    throw new ApiError('Expected JSON response from API', response.status, payload);
  }

  return payload as T;
}
