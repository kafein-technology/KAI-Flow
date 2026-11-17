export interface ApiPaths { API_PREFIX: string; }
export function normalizePath(value: unknown, name: string, fallback?: string): string;
export function resolveApiPaths(values?: Record<string, unknown>): ApiPaths;
export function legacyApiProxyPrefixes(prefix: string): string[];
