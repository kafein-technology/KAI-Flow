import { Routes, Route, useLocation } from "react-router";
import { useEffect } from "react";
import { config } from "./lib/config";
import "./app.css";
import { SnackbarProvider } from "notistack";
import { useThemeStore } from "./stores/theme";
import { AuthProvider, useAuth as useOidcAuth } from "react-oidc-context";
import useAuthStore from "./stores/auth";
import ErrorBoundary from "./components/common/ErrorBoundary";

// Route imports
import Home from "./routes/home";
import Signin from "./routes/signin";
import Register from "./routes/register";
import Workflows from "./routes/workflows";
import Pinned from "./routes/pinned";
import Settings from "./routes/settings";
import Canvas from "./routes/canvas";
import Executions from "./routes/executions";
import Credentials from "./routes/credentials";
import Variables from "./routes/variables";
import Marketplace from "./routes/marketplace";

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
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/signin" element={<Signin />} />
          {!config.IS_ENTERPRISE && <Route path="/register" element={<Register />} />}
          <Route path="/workflows" element={<Workflows />} />
          <Route path="/pinned" element={<Pinned />} />
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
        {isKeycloakEnabled && <AuthSynchronizer />}
      </SnackbarProvider>
    </ErrorBoundary>
  );

  if (isKeycloakEnabled) {
    return <AuthProvider {...oidcConfig}>{content}</AuthProvider>;
  }

  return content;
}
