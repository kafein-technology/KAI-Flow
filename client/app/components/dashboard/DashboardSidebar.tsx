import {
  Play,
  BarChart2,
  Key,
  Database,
  LogOut,
  Store,
  Zap,
  User,
  Bell,
  Search,
  X,
  Clock,
  Heart,
} from "~/components/common/Icon";
import React, { useState, useEffect, useMemo } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { useAuth } from "~/stores/auth";
import { useThemeStore } from "~/stores/theme";
import { ThemeToggle } from "../common/ThemeToggle";
import { useSnackbar } from "notistack";
import { useWorkflows } from "~/stores/workflows";
import { useExecutionsStore } from "~/stores/executions";
import { useUserCredentialStore } from "~/stores/userCredential";
import { useVariableStore } from "~/stores/variables";
import { usePinnedItems } from "~/stores/pinnedItems";
import type {
  Workflow,
  WorkflowExecution,
  UserCredential,
  Variable,
} from "~/types/api";

import { useAuth as useOidcAuth } from "react-oidc-context";
import { resolveIconPath } from "~/lib/iconUtils";

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

const Sidebar = () => {
  const { enqueueSnackbar } = useSnackbar();
  const { user, signOut } = useAuth();
  const oidcAuth = useOidcAuth(); // Keycloak auth hook
  const location = useLocation();
  const router = useNavigate();
  const mode = useThemeStore((s) => s.mode);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);

  // Store hooks
  const { workflows, fetchWorkflows } = useWorkflows();
  const { executions, fetchExecutions } = useExecutionsStore();
  const { userCredentials: credentials, fetchCredentials } =
    useUserCredentialStore();
  const { variables, fetchVariables } = useVariableStore();
  const { getPinnedItems } = usePinnedItems();

  // Fetch data on component mount
  useEffect(() => {
    const loadData = async () => {
      try {
        await Promise.all([
          fetchWorkflows(),
          fetchCredentials(),
          fetchVariables(),
        ]);
      } catch (error) {
        console.error("Failed to load data for search:", error);
      }
    };
    loadData();
  }, [fetchWorkflows, fetchCredentials, fetchVariables]);

  // Search results
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];

    const query = searchQuery.toLowerCase();
    const results: SearchResult[] = [];

    // Search workflows
    workflows.forEach((workflow: Workflow) => {
      if (
        workflow.name.toLowerCase().includes(query) ||
        workflow.description?.toLowerCase().includes(query)
      ) {
        results.push({
          id: workflow.id,
          type: "workflow",
          title: workflow.name,
          description: workflow.description,
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
      if (
        execution.input_text.toLowerCase().includes(query) ||
        execution.status.toLowerCase().includes(query)
      ) {
        results.push({
          id: execution.id,
          type: "execution",
          title: `Execution ${execution.id.slice(0, 8)}`,
          description:
            execution.input_text.slice(0, 50) +
            (execution.input_text.length > 50 ? "..." : ""),
          path: `/executions`,
          icon: <BarChart2 className="w-4 h-4" />,
          metadata: {
            status: execution.status,
            date: new Date(execution.started_at).toLocaleDateString(),
          },
        });
      }
    });

    // Search credentials
    credentials.forEach((credential: UserCredential) => {
      if (
        credential.name.toLowerCase().includes(query) ||
        credential.service_type.toLowerCase().includes(query)
      ) {
        results.push({
          id: credential.id,
          type: "credential",
          title: credential.name,
          description: credential.service_type,
          path: `/credentials`,
          icon: <Key className="w-4 h-4" />,
          metadata: {
            category: credential.service_type,
            date: new Date(credential.created_at).toLocaleDateString(),
          },
        });
      }
    });

    // Search variables
    variables.forEach((variable: Variable) => {
      if (
        variable.name.toLowerCase().includes(query) ||
        variable.value.toLowerCase().includes(query) ||
        variable.type.toLowerCase().includes(query)
      ) {
        results.push({
          id: variable.id,
          type: "variable",
          title: variable.name,
          description: `${variable.type}: ${variable.value.slice(0, 30)}${variable.value.length > 30 ? "..." : ""
            }`,
          path: `/variables`,
          icon: <Database className="w-4 h-4" />,
          metadata: {
            category: variable.type,
            date: new Date(variable.updated_at).toLocaleDateString(),
          },
        });
      }
    });

    return results.slice(0, 8); // Limit to 8 results
  }, [searchQuery, workflows, executions, credentials, variables]);

  const handleSearchFocus = () => {
    setIsSearchFocused(true);
    setShowSearchResults(true);
  };

  const handleSearchBlur = () => {
    // Delay hiding results to allow clicking on them
    setTimeout(() => {
      setIsSearchFocused(false);
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
    <aside className="w-72 h-screen p-4 flex flex-col justify-between bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 text-white border-r border-slate-700/50 transition-all duration-300 ease-in-out backdrop-blur-sm shadow-2xl">
      {/* Header Section */}
      <div className="space-y-6">
        {/* Logo */}
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center space-x-3 group">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg group-hover:shadow-blue-500/25 transition-all duration-300">
              <img src={resolveIconPath("logo.png")} alt="logo" className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                KAI-Fusion
              </h1>
              <p className="text-xs text-slate-400">AI Workflow Platform</p>
            </div>
          </Link>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 brightness-0 invert opacity-50" />
          <input
            type="text"
            placeholder="Search workflows, executions, credentials..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={handleSearchFocus}
            onBlur={handleSearchBlur}
            className="w-full pl-10 pr-10 py-2 bg-slate-800/50 border border-slate-600/50 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all duration-200"
          />
          {searchQuery && (
            <button
              onClick={clearSearch}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400 hover:text-slate-300 transition-colors"
            >
              <X className="w-4 h-4 brightness-0 invert" />
            </button>
          )}

          {/* Search Results Dropdown */}
          {showSearchResults && searchResults.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-slate-800/95 backdrop-blur-sm border border-slate-600/50 rounded-lg shadow-2xl z-50 max-h-80 overflow-y-auto">
              <div className="p-2">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 px-2">
                  Search Results ({searchResults.length})
                </div>
                {searchResults.map((result) => (
                  <button
                    key={`${result.type}-${result.id}`}
                    onClick={() => handleSearchResultClick(result)}
                    className="w-full flex items-center space-x-3 p-3 rounded-lg hover:bg-slate-700/50 transition-all duration-200 text-left group"
                  >
                    <div className="flex items-center justify-center w-8 h-8 bg-slate-700/50 rounded-lg group-hover:bg-slate-600/50 transition-colors">
                      {result.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-medium text-white truncate">
                          {result.title}
                        </span>
                        <span
                          className={`px-2 py-0.5 text-xs rounded-full ${result.type === "workflow"
                              ? "bg-blue-500/20 text-blue-300"
                              : result.type === "execution"
                                ? "bg-green-500/20 text-green-300"
                                : result.type === "credential"
                                  ? "bg-orange-500/20 text-orange-300"
                                  : "bg-purple-500/20 text-purple-300"
                            }`}
                        >
                          {result.type}
                        </span>
                      </div>
                      {result.description && (
                        <p className="text-xs text-slate-400 truncate mt-1">
                          {result.description}
                        </p>
                      )}
                      {result.metadata && (
                        <div className="flex items-center space-x-2 mt-1">
                          {result.metadata.status && (
                            <span className="text-xs text-slate-500">
                              {result.metadata.status}
                            </span>
                          )}
                          {result.metadata.date && (
                            <span className="text-xs text-slate-500 flex items-center">
                              <Clock className="w-3 h-3 mr-1" />
                              {result.metadata.date}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* No Results */}
          {showSearchResults && searchQuery && searchResults.length === 0 && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-slate-800/95 backdrop-blur-sm border border-slate-600/50 rounded-lg shadow-2xl z-50 p-4">
              <div className="text-center">
                <Search className="w-8 h-8 text-slate-500 mx-auto mb-2" />
                <p className="text-sm text-slate-400">
                  No results found for "{searchQuery}"
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Try searching for workflows, executions, or credentials
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1">
          <div className="space-y-2">
            {/* Pinned Items Link */}
            {(() => {
              const pinnedItems = getPinnedItems();
              if (pinnedItems.length > 0) {
                return (
                  <SidebarLink
                    icon={<Heart className="w-5 h-5 brightness-0 invert" />}
                    label="Pinned Items"
                    path="/pinned"
                    active={location.pathname === "/pinned"}
                    badge={`${pinnedItems.length}`}
                  />
                );
              }
              return null;
            })()}

            <SidebarLink
              icon={<Play className="w-5 h-5 brightness-0 invert" />}
              label="Workflows"
              path="/workflows"
              active={location.pathname === "/workflows"}
            />
            <SidebarLink
              icon={<BarChart2 className="w-5 h-5 brightness-0 invert" />}
              label="Executions"
              path="/executions"
              active={location.pathname === "/executions"}
            />
            <SidebarLink
              icon={<Key className="w-5 h-5 brightness-0 invert" />}
              label="Credentials"
              path="/credentials"
              active={location.pathname === "/credentials"}
            />
            <SidebarLink
              icon={<Store className="w-5 h-5 brightness-0 invert" />}
              label="Marketplace"
              path="/marketplace"
              active={location.pathname === "/marketplace"}
            />

            {/* Divider */}
            <div className="h-px bg-gradient-to-r from-transparent via-slate-600/50 to-transparent my-4" />

            {/* Quick Actions */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Quick Actions
              </h3>
              <SidebarLink
                icon={<Zap className="w-5 h-5 brightness-0 invert" />}
                label="New Workflow"
                path="/canvas"
                active={false}
                variant="action"
              />
            </div>
          </div>
        </nav>
      </div>

      {/* Footer Section */}
      <div className="space-y-4">
        {/* User Profile */}
        <button
          onClick={() => router("/settings")}
          className="w-full p-3 bg-slate-800/30 rounded-lg border border-slate-600/30 hover:bg-slate-700/40 hover:border-slate-500/40 transition-all duration-200 group"
        >
          <div className="flex items-center space-x-3">
            <div className="relative">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center shadow-lg group-hover:shadow-lg group-hover:shadow-blue-500/20 transition-all duration-200">
                <User className="w-5 h-5 text-white" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-green-400 rounded-full border-2 border-slate-800" />
            </div>

            <div className="flex-1 min-w-0 text-left">
              <p className="text-sm font-medium text-white truncate group-hover:text-blue-300 transition-colors duration-200">
                {user?.full_name || "Kullanıcı"}
              </p>
              <p className="text-xs text-slate-400 truncate">{user?.email}</p>
            </div>
          </div>
        </button>

        {/* Logout Button */}
        <button
          onClick={handleLogOut}
          className="w-full flex items-center gap-2 px-4 py-3 text-red-400 hover:text-red-300 transition-colors duration-200"
        >
          <LogOut className="w-4 h-4" />
          <span className="text-sm font-medium">Logout</span>
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
  variant = "default",
}: {
  icon: React.ReactNode;
  label: string;
  path: string;
  active: boolean;
  badge?: string;
  variant?: "default" | "action";
}) {
  const getVariantStyles = () => {
    if (variant === "action") {
      return active
        ? "bg-gradient-to-r from-blue-500/20 to-purple-500/20 text-blue-300 border border-blue-500/30"
        : "text-slate-300 hover:bg-gradient-to-r hover:from-blue-500/10 hover:to-purple-500/10 hover:text-blue-300";
    }

    return active
      ? "bg-gradient-to-r from-slate-700/50 to-slate-600/50 text-white border border-slate-500/50"
      : "text-slate-300 hover:bg-slate-700/50 hover:text-white";
  };

  return (
    <Link
      to={path}
      className={`
        flex items-center space-x-3 px-3 py-2.5 rounded-lg 
        transition-all duration-200 group relative
        ${getVariantStyles()}
      `}
    >
      <span className="flex items-center justify-center min-w-[20px] group-hover:scale-110 transition-transform duration-200 [&>img]:brightness-0 [&>img]:invert">
        {icon}
      </span>

      <span className="text-sm font-medium flex-1">{label}</span>
      {badge && (
        <span
          className={`
            px-2 py-0.5 text-xs font-bold rounded-full
            ${badge === "New"
              ? "bg-green-500/20 text-green-300 border border-green-500/30"
              : "bg-orange-500/20 text-orange-300 border border-orange-500/30"
            }
          `}
        >
          {badge}
        </span>
      )}

      {/* Active indicator */}
      {active && (
        <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-1 h-6 bg-gradient-to-b from-blue-400 to-purple-400 rounded-r-full" />
      )}
    </Link>
  );
}
