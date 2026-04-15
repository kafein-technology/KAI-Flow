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
      // Keycloak redirect parametrelerini bekle
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
        setChecking(false);
        navigate("/signin", { replace: true, state: { from: location } });
        return;
      }

      // 2. Kullanıcı yoksa backend'den çek
      if (!user) {
        try {
          const me = await apiClient.get("/auth/me");
          setUser(me);
          setIsAuthenticated(true);
          setChecking(false);
        } catch (err) {
          console.error('Auth check failed:', err);
          // Token bozuksa temizle ve yönlendir
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

  // Auth kontrolü sırasında loading göster
  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  // Auth geçerli değilse null döndür (redirect zaten yapıldı)
  if (!isAuthenticated || !user) {
    return null;
  }

  return <>{children}</>;
}
