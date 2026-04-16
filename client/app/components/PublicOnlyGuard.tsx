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
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const init = async () => {
      // Check if token exists in localStorage
      const accessToken = localStorage.getItem("auth_access_token");

      if (accessToken) {
        try {
          // Initialize with timeout — proceed if not completed within 5 seconds
          await Promise.race([
            initialize(),
            new Promise((_, reject) =>
              setTimeout(() => reject(new Error("Auth init timeout")), 5000)
            ),
          ]);
        } catch (error) {
          console.warn("Auth initialization failed, clearing tokens:", error);
          localStorage.removeItem("auth_access_token");
          localStorage.removeItem("auth_refresh_token");
        }
        setReady(true);
      } else {
        // No token found, set ready immediately
        setReady(true);
      }
    };
    init();
  }, [initialize]);

  useEffect(() => {
    if (ready && isAuthenticated) {
      // Already authenticated → redirect to home
      navigate("/", { replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  // Show loading spinner until ready
  if (!ready) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  // Not authenticated — render children (e.g. signin form)
  return <>{children}</>;
}
