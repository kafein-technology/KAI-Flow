import { Loader2 } from "~/components/common/Icon";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "~/stores/auth";

export default function PublicOnlyGuard({
  children,
}: {
  children: React.ReactNode;
}) {
  const navigate = useNavigate();
  const { isAuthenticated, initialize, isLoading } = useAuth();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const init = async () => {
      // localStorage'da token var mı kontrol et
      const accessToken = localStorage.getItem("auth_access_token");

      if (accessToken) {
        // Token varsa initialize et
        await initialize();
        setReady(true);
      } else {
        // Token yoksa direkt ready yap
        setReady(true);
      }
    };
    init();
  }, [initialize]);

  useEffect(() => {
    if (ready && isAuthenticated) {
      // Giriş yapmışsa → anasayfa /
      navigate("/", { replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  // Token yoksa ve ready ise direkt children'ı göster
  if (!ready) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  // Giriş yapmamışsa, children'ı (örneğin signin formu) göster
  return <>{children}</>;
}
