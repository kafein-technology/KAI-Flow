import { Routes, Route, useLocation } from "react-router";
import { lazy, Suspense, type ReactNode, useEffect } from "react";
import { config } from "./lib/config";
import "./app.css";
import { SnackbarProvider } from "notistack";
import { useThemeStore } from "./stores/theme";
import { AuthProvider, useAuth as useOidcAuth } from "react-oidc-context";
import useAuthStore from "./stores/auth";
import ErrorBoundary from "./components/common/ErrorBoundary";

const Home = lazy(() => import("./routes/home"));
const Signin = lazy(() => import("./routes/signin"));
const Register = lazy(() => import("./routes/register"));
const Workflows = lazy(() => import("./routes/workflows"));
const Settings = lazy(() => import("./routes/settings"));
const Canvas = lazy(() => import("./routes/canvas"));
const Executions = lazy(() => import("./routes/executions"));
const Credentials = lazy(() => import("./routes/credentials"));
const Variables = lazy(() => import("./routes/variables"));
const Marketplace = lazy(() => import("./routes/marketplace"));

const oidcConfig = {
  authority: window.VITE_KEYCLOAK_URL
    ? `${window.VITE_KEYCLOAK_URL}/realms/${window.VITE_KEYCLOAK_REALM}`
    : "",
  client_id: window.VITE_KEYCLOAK_CLIENT_ID || "",
  redirect_uri: typeof window !== "undefined" ? `${window.location.origin}${window.VITE_BASE_PATH || ""}` : "",
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname);
  },
};

function AuthSynchronizer() {
  const { user, isAuthenticated } = useOidcAuth();
  const store = useAuthStore();

  useEffect(() => {
    if (isAuthenticated && user?.access_token) {
      // Check if token is expired - don't write expired tokens to localStorage
      try {
        const payload = JSON.parse(atob(user.access_token.split('.')[1]));
        const isExpired = payload.exp * 1000 < Date.now();
        if (isExpired) {
          console.warn('OIDC token expired, skipping localStorage sync');
          return;
        }
      } catch (e) {
        // If token cannot be parsed, skip writing
        console.warn('Could not parse OIDC token, skipping sync:', e);
        return;
      }

      localStorage.setItem("auth_access_token", user.access_token);
      if (user.refresh_token) {
        localStorage.setItem("auth_refresh_token", user.refresh_token);
      }

      // Mark auth source as Keycloak
      sessionStorage.setItem("auth_source", "keycloak");
    } else if (
      !isAuthenticated &&
      !user &&
      store.isAuthenticated &&
      localStorage.getItem("auth_access_token")
    ) {
      // Keycloak logout detected or sync mismatch
      // Only force logout if the previous session was from Keycloak
      if (sessionStorage.getItem("auth_source") === "keycloak") {
        store.signOut();
        sessionStorage.removeItem("auth_source");
      }
    }
  }, [isAuthenticated, user, store.isAuthenticated, store.initialize, store.signOut]);
  return null;
}

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}

function ProductSurface({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const excludedRoutes = ["/canvas", "/signin", "/register"];
  const isProductPage = !excludedRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );

  return (
    <div className={isProductPage ? "kai-product-surface" : undefined}>
      {children}
    </div>
  );
}

function RouteFallback() {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-[var(--kai-bg-deep)]"
      role="status"
      aria-label="Loading page"
    >
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-700 border-t-blue-500" />
    </div>
  );
}

export default function App() {
  const { mode } = useThemeStore();
  const isKeycloakEnabled = !!oidcConfig.authority && !!oidcConfig.client_id;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", mode);
    document.documentElement.className = "h-full";
    document.body.className = "h-full";
  }, [mode]);

  const content = (
    <ErrorBoundary>
      <SnackbarProvider
        maxSnack={3}
        anchorOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <ScrollToTop />
        <ProductSurface>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/signin" element={<Signin />} />
              {!config.IS_ENTERPRISE && <Route path="/register" element={<Register />} />}
              <Route path="/workflows" element={<Workflows />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/canvas" element={<Canvas />} />
              <Route path="/executions" element={<Executions />} />
              <Route path="/credentials" element={<Credentials />} />
              <Route path="/variables" element={<Variables />} />
              {!config.IS_ENTERPRISE && <Route path="/marketplace" element={<Marketplace />} />}
              <Route
                path="*"
                element={
                  <main className="pt-16 p-4 container mx-auto">
                    <h1>404</h1>
                    <p>The requested page could not be found.</p>
                  </main>
                }
              />
            </Routes>
          </Suspense>
        </ProductSurface>
        {isKeycloakEnabled && <AuthSynchronizer />}
      </SnackbarProvider>
    </ErrorBoundary>
  );

  if (isKeycloakEnabled) {
    return <AuthProvider {...oidcConfig}>{content}</AuthProvider>;
  }

  return content;
}
