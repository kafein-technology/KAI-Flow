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
      // If logged in, redirect to home page
      navigate("/", { replace: true });
    }
  }, [initializing, isLoading, isAuthenticated, navigate]);

  // Show spinner during initialize or loading
  if (initializing || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  // If not logged in, show children (e.g., signin form)
  return <>{children}</>;
}
