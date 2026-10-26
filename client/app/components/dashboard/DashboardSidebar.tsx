import {
  Play,
  BarChart2,
  Key,
  Database,
  LogOut,
  Store,
  User,
  Search,
  X,
  LayoutDashboard,
  LoaderCircle,
  Settings,
  ChevronUp,
} from "lucide-react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { useAuth } from "~/stores/auth";
import { useSnackbar } from "notistack";
import { useWorkflows } from "~/stores/workflows";
import { useExecutionsStore } from "~/stores/executions";
import { useUserCredentialStore } from "~/stores/userCredential";
import { useVariableStore } from "~/stores/variables";
import type {
  Workflow,
  WorkflowExecution,
  UserCredential,
  Variable,
} from "~/types/api";

import { useAuth as useOidcAuth } from "react-oidc-context";
import { BrandLogo } from "~/components/common/BrandLogo";
import { config } from "~/lib/config";

interface SearchResult {
  id: string;
  type: "workflow" | "execution" | "credential" | "variable";
  title: string;
  description?: string;
  path: string;
  icon: React.ReactNode;
  metadata?: {
    status?: string;
    date?: string;
    category?: string;
  };
}

const normalizeSearchValue = (value: unknown) =>
  String(value ?? "").trim().toLowerCase();

const Sidebar = () => {
  const { enqueueSnackbar } = useSnackbar();
  const { user, signOut } = useAuth();
  const oidcAuth = useOidcAuth(); // Keycloak auth hook
  const location = useLocation();
  const router = useNavigate();

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [searchDataLoaded, setSearchDataLoaded] = useState(false);
  const [searchDataLoading, setSearchDataLoading] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Store hooks
  const { workflows, fetchWorkflows } = useWorkflows();
  const { executions, fetchAllExecutions } = useExecutionsStore();
  const { userCredentials: credentials, fetchCredentials } =
    useUserCredentialStore();
  const { variables, fetchVariables } = useVariableStore();

  // Search results
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];

    const query = normalizeSearchValue(searchQuery);
    const results: SearchResult[] = [];

    // Search workflows
    workflows.forEach((workflow: Workflow) => {
      const name = String(workflow.name ?? "");
      const description = String(workflow.description ?? "");
      if (
        normalizeSearchValue(name).includes(query) ||
        normalizeSearchValue(description).includes(query)
      ) {
        results.push({
          id: workflow.id,
          type: "workflow",
          title: name || "Untitled workflow",
          description,
          path: `/workflows`,
          icon: <Play className="w-4 h-4" />,
          metadata: {
            status: workflow.is_public ? "Public" : "Private",
            date: new Date(workflow.updated_at).toLocaleDateString(),
          },
        });
      }
    });

    // Search executions
    executions.forEach((execution: WorkflowExecution) => {
      const inputText = String(execution.input_text ?? "");
      const status = String(execution.status ?? "");
      if (
        normalizeSearchValue(inputText).includes(query) ||
        normalizeSearchValue(status).includes(query)
      ) {
        results.push({
          id: execution.id,
          type: "execution",
          title: `Execution ${execution.id.slice(0, 8)}`,
          description:
            inputText.slice(0, 50) +
            (inputText.length > 50 ? "..." : ""),
          path: `/executions`,
          icon: <BarChart2 className="w-4 h-4" />,
          metadata: {
            status,
            date: new Date(execution.started_at).toLocaleDateString(),
          },
        });
      }
    });

    // Search credentials
    credentials.forEach((credential: UserCredential) => {
      const name = String(credential.name ?? "");
      const serviceType = String(credential.service_type ?? "");
      if (
        normalizeSearchValue(name).includes(query) ||
        normalizeSearchValue(serviceType).includes(query)
      ) {
        results.push({
          id: credential.id,
          type: "credential",
          title: name || "Unnamed credential",
          description: serviceType,
          path: `/credentials`,
          icon: <Key className="w-4 h-4" />,
          metadata: {
            category: serviceType,
            date: new Date(credential.created_at).toLocaleDateString(),
          },
        });
      }
    });

    // Search variables
    variables.forEach((variable: Variable) => {
      const name = String(variable.name ?? "");
      const value = String(variable.value ?? "");
      const type = String(variable.type ?? "");
      if (
        normalizeSearchValue(name).includes(query) ||
        normalizeSearchValue(value).includes(query) ||
        normalizeSearchValue(type).includes(query)
      ) {
        results.push({
          id: variable.id,
          type: "variable",
          title: name || "Unnamed variable",
          description: `${type}: ${value.slice(0, 30)}${value.length > 30 ? "..." : ""
            }`,
          path: `/variables`,
          icon: <Database className="w-4 h-4" />,
          metadata: {
            category: type,
            date: new Date(variable.updated_at).toLocaleDateString(),
          },
        });
      }
    });

    return results.slice(0, 8); // Limit to 8 results
  }, [searchQuery, workflows, executions, credentials, variables]);

  const handleSearchFocus = async () => {
    setShowSearchResults(true);
    if (searchDataLoaded || searchDataLoading) return;

    setSearchDataLoading(true);
    try {
      await Promise.allSettled([
        fetchWorkflows(),
        fetchAllExecutions(true),
        fetchCredentials(),
        fetchVariables(),
      ]);
      setSearchDataLoaded(true);
    } finally {
      setSearchDataLoading(false);
    }
  };

  const handleSearchBlur = () => {
    // Delay hiding results to allow clicking on them
    setTimeout(() => {
      setShowSearchResults(false);
    }, 200);
  };

  const handleSearchResultClick = (result: SearchResult) => {
    setSearchQuery("");
    setShowSearchResults(false);
    router(result.path);
  };

  const clearSearch = () => {
    setSearchQuery("");
    setShowSearchResults(false);
  };

  useEffect(() => {
    const closeUserMenu = (event: MouseEvent) => {
      if (!userMenuRef.current?.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    };

    const closeUserMenuWithEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowUserMenu(false);
    };

    document.addEventListener("mousedown", closeUserMenu);
    document.addEventListener("keydown", closeUserMenuWithEscape);
    return () => {
      document.removeEventListener("mousedown", closeUserMenu);
      document.removeEventListener("keydown", closeUserMenuWithEscape);
    };
  }, []);

  useEffect(() => {
    setShowUserMenu(false);
  }, [location.pathname]);

  const isKeycloakEnabled = !!window.VITE_KEYCLOAK_URL && !!window.VITE_KEYCLOAK_CLIENT_ID;

  const handleLogOut = async () => {
    try {
      if (isKeycloakEnabled && oidcAuth?.signoutRedirect) {
        // Keycloak logout
        await signOut(); // Clear local state first
        // Keycloak çıkışından sonra signin sayfasına yönlendirilebilmesi için post_logout_redirect_uri parametresi eklenebilir
        // Ancak oidc-client-ts bunu config'den alır.

        const postLogoutRedirectUri = typeof window !== 'undefined'
          ? `${window.location.origin}${window.VITE_BASE_PATH && window.VITE_BASE_PATH !== "/"
            ? window.VITE_BASE_PATH
            : ""
          }/signin`
          : "";

        await oidcAuth.signoutRedirect({ post_logout_redirect_uri: postLogoutRedirectUri });
      } else {
        // Normal logout
        await signOut();
        router("/signin");
      }

      enqueueSnackbar("Başarıyla çıkış yapıldı", {
        variant: "success",
      });
    } catch (error) {
      console.error("Logout failed:", error);
      enqueueSnackbar("Çıkış yapılırken hata oluştu", {
        variant: "error",
      });
      // Fallback redirect
      router("/signin");
    }
  };

  return (
    <aside className="kai-sidebar relative z-30 flex h-screen w-[278px] shrink-0 flex-col border-r border-[var(--kai-border)] bg-[var(--kai-dashboard-sidebar-bg)] text-zinc-100">
      <header className="flex h-16 shrink-0 items-center border-b border-[var(--kai-border)] px-5">
        <Link to="/" className="flex items-center gap-3 rounded-md focus-visible:outline-none">
          <BrandLogo className="h-8 w-8 shrink-0 object-contain" />
          <span className="text-[15px] font-semibold tracking-[-0.025em] text-[var(--kai-text)]">
            KAI Flow
          </span>
        </Link>
      </header>

      <div className="relative mx-3 mb-3 mt-3">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--kai-text-disabled)]" />
          <input
            type="text"
            placeholder="Search workspace"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={handleSearchFocus}
            onBlur={handleSearchBlur}
            className="h-9 w-full rounded-lg border border-[var(--kai-dashboard-search-border)] bg-[var(--kai-surface)] pl-9 pr-8 text-xs text-[var(--kai-sidebar-control-text)] outline-none placeholder:text-[var(--kai-placeholder)] focus:border-[var(--kai-accent)] focus:ring-2 focus:ring-[var(--kai-accent)]/15"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={clearSearch}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-200"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}

          {showSearchResults && searchDataLoading && (
            <div className="absolute left-0 right-0 top-full z-50 mt-2 flex items-center gap-2 rounded-lg border border-[var(--kai-border-muted)] bg-[var(--kai-surface-raised)] px-3 py-3 text-xs text-zinc-300 shadow-2xl">
              <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
              Loading workspace…
            </div>
          )}

          {showSearchResults && !searchDataLoading && searchResults.length > 0 && (
            <div className="absolute left-0 right-0 top-full z-50 mt-2 max-h-80 overflow-y-auto rounded-lg border border-[var(--kai-border-muted)] bg-[var(--kai-surface-raised)] p-1.5 shadow-2xl">
                <div className="px-2 pb-1.5 pt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-600">
                  Results
                </div>
                {searchResults.map((result) => (
                  <button
                    type="button"
                    key={`${result.type}-${result.id}`}
                    onClick={() => handleSearchResultClick(result)}
                    className="group flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left hover:bg-[var(--kai-border)]"
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--kai-border-muted)] bg-[var(--kai-surface)] text-zinc-300">
                      {result.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-xs font-medium text-zinc-200">
                          {result.title}
                        </span>
                        <span className="text-[10px] capitalize text-zinc-600">
                          {result.type}
                        </span>
                      </div>
                      {result.description && (
                        <p className="mt-0.5 truncate text-[11px] text-zinc-500">
                          {result.description}
                        </p>
                      )}
                    </div>
                  </button>
                ))}
            </div>
          )}

          {showSearchResults && !searchDataLoading && searchQuery && searchResults.length === 0 && (
            <div className="absolute left-0 right-0 top-full z-50 mt-2 rounded-lg border border-[var(--kai-border-muted)] bg-[var(--kai-surface-raised)] px-3 py-4 text-center shadow-2xl">
              <p className="text-xs text-zinc-400">No results for “{searchQuery}”</p>
            </div>
          )}
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2">
          <p className="sr-only">Workspace</p>
          <div className="space-y-0.5">
            <SidebarLink
              icon={<LayoutDashboard className="h-[18px] w-[18px]" />}
              label="Dashboard"
              path="/"
              active={location.pathname === "/"}
            />
            <SidebarLink
              icon={<Play className="h-[18px] w-[18px]" />}
              label="Workflows"
              path="/workflows"
              active={location.pathname === "/workflows"}
            />
            <SidebarLink
              icon={<BarChart2 className="h-[18px] w-[18px]" />}
              label="Executions"
              path="/executions"
              active={location.pathname === "/executions"}
            />
          </div>

          <div className="my-3 border-t border-[var(--kai-border)]" />
          <p className="sr-only">Manage</p>
          <div className="space-y-0.5">
            <SidebarLink
              icon={<Key className="h-[18px] w-[18px]" />}
              label="Credentials"
              path="/credentials"
              active={location.pathname === "/credentials"}
            />
            <SidebarLink
              icon={<Database className="h-[18px] w-[18px]" />}
              label="Variables"
              path="/variables"
              active={location.pathname === "/variables"}
            />
            {!config.IS_ENTERPRISE && (
              <SidebarLink
                icon={<Store className="h-[18px] w-[18px]" />}
                label="Marketplace"
                path="/marketplace"
                active={location.pathname === "/marketplace"}
              />
            )}

          </div>
      </nav>

      <div ref={userMenuRef} className="relative mt-4 border-t border-[var(--kai-border)] p-3">
        {showUserMenu && (
          <div
            id="sidebar-user-menu"
            role="menu"
            className="absolute bottom-[calc(100%+8px)] left-3 right-3 z-50 rounded-lg border border-[var(--kai-border-muted)] bg-[var(--kai-surface-raised)] p-1.5 shadow-2xl"
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => router("/settings")}
              className="flex h-10 w-full items-center gap-3 rounded-md px-3 text-sm text-[var(--kai-sidebar-menu-text)] hover:bg-[var(--kai-border)]"
            >
              <Settings className="h-4 w-4 text-[var(--kai-sidebar-menu-icon)]" />
              Settings
            </button>
            <div className="my-1 border-t border-[var(--kai-input-border)]" />
            <button
              type="button"
              role="menuitem"
              onClick={handleLogOut}
              className="flex h-10 w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-[var(--kai-danger-menu-text)] transition-colors hover:bg-[var(--kai-danger-menu-bg)] hover:text-[var(--kai-danger-menu-text-hover)]"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </div>
        )}

        <button
          type="button"
          aria-expanded={showUserMenu}
          aria-controls="sidebar-user-menu"
          onClick={() => setShowUserMenu((isOpen) => !isOpen)}
          className="group flex min-h-14 w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left hover:bg-[var(--kai-input-bg)]"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--kai-surface-hover-deep)] text-[var(--kai-sidebar-user-icon)]">
            <User className="h-[18px] w-[18px]" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-[var(--kai-sidebar-user-name)]">
              {user?.full_name || "User"}
            </span>
            <span className="mt-0.5 block truncate text-[11px] text-[var(--kai-sidebar-user-meta)]">
              {user?.email}
            </span>
          </span>
          <ChevronUp
            className={`h-4 w-4 text-[var(--kai-sidebar-chevron)] transition-transform ${showUserMenu ? "rotate-180" : ""}`}
          />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;

function SidebarLink({
  icon,
  label,
  path,
  active,
  badge,
}: {
  icon: React.ReactNode;
  label: string;
  path: string;
  active: boolean;
  badge?: string;
}) {
  return (
    <Link
      to={path}
      aria-current={active ? "page" : undefined}
      className={`group relative flex h-11 items-center gap-3 rounded-lg px-3 text-[15px] font-medium transition-colors ${
        active
          ? "bg-[var(--kai-surface-hover-subtle)] text-white before:absolute before:-left-0.5 before:h-[18px] before:w-[3px] before:rounded-full before:bg-[var(--kai-accent)]"
                : "text-[var(--kai-sidebar-item-text)] hover:bg-[var(--kai-sidebar-item-hover-bg)] hover:text-white"
      }`}
    >
          <span className={active ? "text-white" : "text-[var(--kai-sidebar-icon-text)] group-hover:text-zinc-200"}>
        {icon}
      </span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {badge && (
          <span className="rounded-md bg-[var(--kai-sidebar-count-bg)] px-1.5 py-0.5 text-[10px] font-medium text-zinc-300">
          {badge}
        </span>
      )}
    </Link>
  );
}
