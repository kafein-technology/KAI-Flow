import { Loader2 } from "lucide-react";
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
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    const init = async () => {
      try {
        await initialize();
      } catch (error) {
        console.error('Initialize failed:', error);
      } finally {
        setInitializing(false);
      }
    };
    init();
  }, [initialize]);

  useEffect(() => {
    if (!initializing && !isLoading && isAuthenticated) {
      // Giriş yapmışsa → anasayfa /
      navigate("/", { replace: true });
    }
  }, [initializing, isLoading, isAuthenticated, navigate]);

  // Initialize veya loading sırasında spinner göster
  if (initializing || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  // Giriş yapmamışsa, children'ı (örneğin signin formu) göster
  return <>{children}</>;
}
