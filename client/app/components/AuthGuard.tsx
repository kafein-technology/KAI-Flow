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

      // 1. Token yoksa signin'e yönlendir
      if (!apiClient.isAuthenticated()) {
        setShouldRedirect(true);
        return;
      }

      // 2. Kullanıcı yoksa backend'den çek
      if (!user) {
        try {
          const me = await apiClient.get("/auth/me");
          setUser(me);
          setIsAuthenticated(true);
        } catch (err) {
          // Token bozuksa interceptor zaten yönlendirir
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

  // Auth durumu değişirse ve geçerli değilse yönlendir
  useEffect(() => {
    if (!checking && (!isAuthenticated || !user)) {
      setShouldRedirect(true);
    }
  }, [checking, isAuthenticated, user]);

  // Auth kontrolü sırasında veya kullanıcı yoksa loading göster
  if (checking || !isAuthenticated || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}
