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
  const [shouldRedirect, setShouldRedirect] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
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

      // 1. No token — redirect to signin
      if (!apiClient.isAuthenticated()) {
        setShouldRedirect(true);
        return;
      }

      // 2. No user in store — fetch from backend
      if (!user) {
        try {
          const me = await Promise.race([
            apiClient.get("/auth/me"),
            new Promise((_, reject) =>
              setTimeout(() => reject(new Error("Auth check timeout")), 5000)
            ),
          ]);
          setUser(me as any);
          setIsAuthenticated(true);
        } catch (err) {
          // Token invalid or timeout — clear tokens and redirect to signin
          console.warn("AuthGuard: auth check failed:", err);
          localStorage.removeItem("auth_access_token");
          localStorage.removeItem("auth_refresh_token");
          setUser(null);
          setIsAuthenticated(false);
          setChecking(false);
          setShouldRedirect(true);
          return;
        }
      }

      setChecking(false);
    };

    checkAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redirect effect
  useEffect(() => {
    if (shouldRedirect) {
      navigate("/signin", { replace: true, state: { from: location } });
    }
  }, [shouldRedirect, navigate, location]);

  // If auth state changes and becomes invalid, redirect
  useEffect(() => {
    if (!checking && (!isAuthenticated || !user)) {
      setShouldRedirect(true);
    }
  }, [checking, isAuthenticated, user]);

  // Show loading during auth check or when user is not loaded
  if (checking || !isAuthenticated || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}
