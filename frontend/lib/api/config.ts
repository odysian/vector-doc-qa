const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Builds full URL from a backend path. */
export function fullUrl(path: string): string {
  return `${API_URL}${path}`;
}
