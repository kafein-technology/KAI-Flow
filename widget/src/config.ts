// Standalone widget configuration; does not depend on the client package.
export interface WidgetConfig { API_PREFIX: string; }

const normalize = (value: string): string => {
    const path = value.trim().replace(/^\/+|\/+$/g, '');
    if (!path || path.split('/').some(part => !/^[A-Za-z0-9._~-]+$/.test(part) || part === '.' || part === '..')) {
        throw new Error('API_PREFIX must be a non-empty URL path');
    }
    return `/${path}`;
};

const getWidgetConfig = (): WidgetConfig => {
    const prefix = typeof window === 'undefined' ? undefined : (window as any).API_PREFIX;
    return { API_PREFIX: normalize(prefix || '/kai/api/v1') };
};

export const config = getWidgetConfig();
