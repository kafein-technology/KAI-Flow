// components/AuthGuard.tsx
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router";
import { apiClient } from "~/lib/api-client";
import { useAuth } from "~/stores/auth";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, setUser, setIsAuthenticated } = useAuth();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      // Wait for Keycloak redirect parameters
      const searchParams = new URLSearchParams(window.location.search);
      if (searchParams.has("code") && searchParams.has("state")) {
        let retries = 0;
        while (retries < 10) { 
          await new Promise((resolve) => setTimeout(resolve, 500));
          const currentParams = new URLSearchParams(window.location.search);
          if (!currentParams.has("code")) {
            break;
          }
          retries++;
        }
      }

      // 1. If no token, redirect to signin
      if (!apiClient.isAuthenticated()) {
        setChecking(false);
        navigate("/signin", { replace: true, state: { from: location } });
        return;
      }

      // 2. If no user, fetch from backend
      if (!user) {
        try {
          const me = await apiClient.get("/auth/me");
          setUser(me);
          setIsAuthenticated(true);
          setChecking(false);
        } catch (err) {
          console.error('Auth check failed:', err);
          // If token is invalid, clear and redirect
          localStorage.removeItem('auth_access_token');
          localStorage.removeItem('auth_refresh_token');
          setUser(null);
          setIsAuthenticated(false);
          setChecking(false);
          navigate("/signin", { replace: true, state: { from: location } });
        }
      } else {
        setChecking(false);
      }
    };

    checkAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Show loading during auth check
  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  // Return null if auth is invalid (redirect already done)
  if (!isAuthenticated || !user) {
    return null;
  }

  return <>{children}</>;
}
