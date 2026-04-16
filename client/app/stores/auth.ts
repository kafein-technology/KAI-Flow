import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import Keycloak from 'keycloak-js';
import AuthService from '~/services/authService';
import type { 
  UserResponse, 
  SignUpRequest, 
  SignInRequest,
  AuthResponse,
  UserUpdateProfile
} from '~/services/authService';

interface AuthState {
  // State
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  keycloak: Keycloak | null;
  
  // Actions
  initialize: () => Promise<void>;
  signUp: (data: SignUpRequest) => Promise<void>;
  signIn: (data: SignInRequest) => Promise<void>;
  signOut: () => Promise<void>;
  getProfile: () => Promise<void>;
  updateProfile: (data: UserUpdateProfile) => Promise<void>;
  clearError: () => void;
  setUser: (user: UserResponse | null) => void;
  setIsAuthenticated: (auth: boolean) => void;
  setKeycloak: (keycloak: Keycloak) => void;
}

export const useAuthStore = create<AuthState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    user: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    keycloak: null,

    // Initialize auth state from localStorage
    initialize: async () => {
      set({ isLoading: true });
      
      const accessToken = localStorage.getItem('auth_access_token');
      
      if (!accessToken) {
        // If no token, set state to false directly
        set({ 
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: null
        });
        return;
      }

      // If token exists, validate it
      try {
        const user = await AuthService.getProfile();
        set({ 
          user,
          isAuthenticated: true,
          isLoading: false,
          error: null
        });
      } catch (error: any) {
        // Token expired or invalid, clear it
        console.error('Token validation failed:', error);
        localStorage.removeItem('auth_access_token');
        localStorage.removeItem('auth_refresh_token');
        set({ 
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: null
        });
      }
    },

    // Actions
    signUp: async (data: SignUpRequest) => {
      set({ isLoading: true, error: null });
      
      try {
        const response: AuthResponse = await AuthService.signUp(data);
        
        // Store tokens in localStorage
        localStorage.setItem('auth_access_token', response.access_token);
        localStorage.setItem('auth_refresh_token', response.refresh_token);
        
        set({ 
          user: response.user,
          isAuthenticated: true,
          isLoading: false,
          error: null
        });
      } catch (error: any) {
        set({ 
          isLoading: false,
          error: error.response?.data?.detail || error.message || 'Failed to sign up'
        });
        throw error;
      }
    },

    signIn: async (data: SignInRequest) => {
      set({ isLoading: true, error: null });
      
      try {
        const response: AuthResponse = await AuthService.signIn(data);
        
        // Store tokens in localStorage
        localStorage.setItem('auth_access_token', response.access_token);
        localStorage.setItem('auth_refresh_token', response.refresh_token);
        
        set({ 
          user: response.user,
          isAuthenticated: true,
          isLoading: false,
          error: null
        });
      } catch (error: any) {
        set({ 
          isLoading: false,
          error: error.response?.data?.detail || error.message || 'Failed to sign in'
        });
        throw error;
      }
    },

    signOut: async () => {
      // Clear state first
      set({ 
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null
      });
      
      // Clear tokens from localStorage
      localStorage.removeItem('auth_access_token');
      localStorage.removeItem('auth_refresh_token');
      
      // Make API call in background
      try {
        await AuthService.signOut();
      } catch (error) {
        console.error('Sign out API call failed:', error);
      }
    },

    getProfile: async () => {
      set({ isLoading: true, error: null });
      
      try {
        const user = await AuthService.getProfile();
        set({ 
          user,
          isAuthenticated: true,
          isLoading: false,
          error: null
        });
      } catch (error: any) {
        set({ 
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: error.message || 'Failed to get profile'
        });
        throw error;
      }
    },

    updateProfile: async (data: UserUpdateProfile) => {
      const currentState = get();
      set({ isLoading: true, error: null });
      
      try {
        const updatedUser = await AuthService.updateProfile(data);
        set({ 
          user: updatedUser,
          isLoading: false,
          error: null
        });
      } catch (error: any) {
        set({ 
          user: currentState.user, // Revert to current user on error
          isLoading: false,
          error: error.response?.data?.detail || error.message || 'Failed to update profile'
        });
        throw error;
      }
    },

    clearError: () => {
      set({ error: null });
    },

    setUser: (user: UserResponse | null) => {
      set({ user });
    },

    setIsAuthenticated: (isAuthenticated: boolean) => {
      set({ isAuthenticated });
    },

    setKeycloak: (keycloak: Keycloak) => {
      set({ keycloak });
    },
  }))
);

// Helper hook for common auth operations
export const useAuth = () => {
  const store = useAuthStore();
  
  return {
    // State
    user: store.user,
    isAuthenticated: store.isAuthenticated,
    isLoading: store.isLoading,
    error: store.error,
    
    // Actions
    initialize: store.initialize,
    signUp: store.signUp,
    signIn: store.signIn,
    signOut: store.signOut,
    getProfile: store.getProfile,
    updateProfile: store.updateProfile,
    clearError: store.clearError,
    setUser: store.setUser,
    setIsAuthenticated: store.setIsAuthenticated,
    keycloak: store.keycloak,
    setKeycloak: store.setKeycloak,
  };
};

export default useAuthStore;