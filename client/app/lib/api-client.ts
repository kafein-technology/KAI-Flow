import axios, { type AxiosInstance, type AxiosResponse, type AxiosError } from 'axios';
import { API_ENDPOINTS } from './config';

// API Response types
export interface ApiResponse<T = any> {
    data: T;
    message?: string;
    success: boolean;
}

export interface ApiError {
    message: string;
    status: number;
    code?: string;
    details?: any;
}

// Auth token management
class TokenManager {
    private static readonly ACCESS_TOKEN_KEY = 'auth_access_token';
    private static readonly REFRESH_TOKEN_KEY = 'auth_refresh_token';

    static getAccessToken(): string | null {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(this.ACCESS_TOKEN_KEY);
    }

    static setAccessToken(token: string): void {
        if (typeof window === 'undefined') return;
        localStorage.setItem(this.ACCESS_TOKEN_KEY, token);
    }

    static getRefreshToken(): string | null {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(this.REFRESH_TOKEN_KEY);
    }

    static setRefreshToken(token: string): void {
        if (typeof window === 'undefined') return;
        localStorage.setItem(this.REFRESH_TOKEN_KEY, token);
    }

    static clearTokens(): void {
        if (typeof window === 'undefined') return;
        localStorage.removeItem(this.ACCESS_TOKEN_KEY);
        localStorage.removeItem(this.REFRESH_TOKEN_KEY);
    }

    static hasValidToken(): boolean {
        return !!this.getAccessToken();
    }
}

// API Client class
class ApiClient {
    private instance: AxiosInstance;
    private isRefreshing = false;
    private failedQueue: Array<{
        resolve: (value: any) => void;
        reject: (error: any) => void;
    }> = [];

    constructor() {
        // Create axios instance
        this.instance = axios.create({
            baseURL: `${window.VITE_API_BASE_URL}${window.VITE_API_VERSION}`,
            timeout: 120000, // 2 minutes timeout for long AI operations
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // Setup interceptors
        this.setupInterceptors();
    }

    private setupInterceptors(): void {
        // Request interceptor - add auth token
        this.instance.interceptors.request.use(
            (config) => {
                const token = TokenManager.getAccessToken();
                if (token) {
                    config.headers.Authorization = `Bearer ${token}`;
                }
                return config;
            },
            (error) => Promise.reject(error)
        );

        // Response interceptor - handle errors and token refresh
        this.instance.interceptors.response.use(
            (response: AxiosResponse) => response,
            async (error: AxiosError) => {
                const originalRequest = error.config as any;

                // Skip interceptor logic for auth endpoints
                if (originalRequest.url?.includes('/auth/signin') || originalRequest.url?.includes('/auth/signup')) {
                    return Promise.reject(this.handleError(error));
                }

                if (error.response?.status === 401 && !originalRequest._retry) {
                    if (this.isRefreshing) {
                        // If refresh is already in progress, queue the request
                        return new Promise((resolve, reject) => {
                            this.failedQueue.push({ resolve, reject });
                        }).then(token => {
                            originalRequest.headers.Authorization = `Bearer ${token}`;
                            return this.instance(originalRequest);
                        }).catch(err => {
                            return Promise.reject(err);
                        });
                    }

                    originalRequest._retry = true;
                    this.isRefreshing = true;

                    try {
                        const refreshToken = TokenManager.getRefreshToken();
                        if (refreshToken) {
                            // Try to refresh token
                            const response = await this.instance.post(API_ENDPOINTS.AUTH.REFRESH, {
                                refresh_token: refreshToken
                            });

                            const newToken = response.data?.data?.access_token || response.data?.access_token;
                            TokenManager.setAccessToken(newToken);

                            // Process the failed queue
                            this.processQueue(null, newToken);

                            // Retry the original request
                            originalRequest.headers.Authorization = `Bearer ${newToken}`;
                            return this.instance(originalRequest);
                        } else {
                            this.processQueue(new Error('No refresh token'), null);
                            TokenManager.clearTokens();
                            // Redirect to login only if not already on signin page
                            if (typeof window !== 'undefined' && !window.location.pathname.endsWith('/signin')) {
                                const basePath = window.VITE_BASE_PATH || '';
                                window.location.replace(`${basePath}/signin`);
                            }
                            return Promise.reject(new Error('Authentication failed - no refresh token'));
                        }
                    } catch (refreshError) {
                        this.processQueue(refreshError, null);
                        TokenManager.clearTokens();
                        // Redirect to login only if not already on signin page
                        if (typeof window !== 'undefined' && !window.location.pathname.endsWith('/signin')) {
                            const basePath = window.VITE_BASE_PATH || '';
                            window.location.replace(`${basePath}/signin`);
                        }
                        return Promise.reject(refreshError);
                    } finally {
                        this.isRefreshing = false;
                    }
                }

                return Promise.reject(this.handleError(error));
            }
        );
    }

    private processQueue(error: any, token: string | null = null): void {
        this.failedQueue.forEach(({ resolve, reject }) => {
            if (error) {
                reject(error);
            } else {
                resolve(token);
            }
        });

        this.failedQueue = [];
    }

    private handleError(error: AxiosError): ApiError {
        if (window.VITE_ENABLE_LOGGING === 'true') {
            console.error('API Error:', error);
        }

        let apiError: ApiError = {
            message: 'An unexpected error occurred',
            status: 500,
        };

        if (error.response) {
            const errorData = error.response.data as any;

            // 🔥 Burayı güncelledik
            const message =
                errorData?.message ||
                errorData?.detail || // <--- burası önemli
                error.message;

            apiError = {
                message,
                status: error.response.status,
                code: errorData?.code,
                details: errorData?.details,
            };
        } else if (error.request) {
            apiError = {
                message: 'Network error - please check your connection',
                status: 0,
            };
        } else {
            apiError = {
                message: error.message,
                status: 0,
            };
        }

        return apiError;
    }


    // Generic HTTP methods
    async get<T = any>(url: string, config?: any): Promise<T> {
        const response = await this.instance.get(url, config);
        return response.data;
    }

    async post<T = any>(url: string, data?: any, config?: any): Promise<T> {
        const response = await this.instance.post(url, data, config);
        return response.data;
    }

    async put<T = any>(url: string, data?: any, config?: any): Promise<T> {
        const response = await this.instance.put(url, data, config);
        return response.data;
    }

    async delete<T = any>(url: string, config?: any): Promise<T> {
        const response = await this.instance.delete(url, config);
        return response.data;
    }

    async patch<T = any>(url: string, data?: any, config?: any): Promise<T> {
        const response = await this.instance.patch(url, data, config);
        return response.data;
    }

    // Utility methods
    setAuthToken(token: string): void {
        TokenManager.setAccessToken(token);
    }

    clearAuth(): void {
        TokenManager.clearTokens();
    }

    isAuthenticated(): boolean {
        return TokenManager.hasValidToken();
    }

    getBaseURL(): string {
        return `${window.VITE_API_BASE_URL}${window.VITE_API_VERSION}`;
    }

    getAccessToken(): string | null {
        return TokenManager.getAccessToken();
    }
}

// Export singleton instance
export const apiClient = new ApiClient();
export { TokenManager };

// Export specific error classes for better error handling
export class NetworkError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'NetworkError';
    }
}

export class AuthenticationError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'AuthenticationError';
    }
}

export class ValidationError extends Error {
    constructor(message: string, public details?: any) {
        super(message);
        this.name = 'ValidationError';
    }
} 