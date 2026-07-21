import React, { useEffect, useState, useMemo, useCallback } from "react";
import {
  Copy,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Search,
  Filter,
  Star,
  TrendingUp,
  Clock,
  Users,
  Download,
  Grid,
  List,
} from "lucide-react";
import {
  prebuiltTemplates,
  type MarketplaceCategory as TemplateCategory,
  type PrebuiltTemplate,
} from "~/data/prebuiltTemplates";
import { useNavigate } from "react-router";
import { useSnackbar } from "notistack";
import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import { useWorkflows } from "~/stores/workflows";
import { usePinnedItems } from "~/stores/pinnedItems";
import { timeAgo } from "~/lib/dateFormatter";
import AuthGuard from "~/components/AuthGuard";
import Loading from "~/components/Loading";
import PinButton from "~/components/common/PinButton";
import * as LucideIcons from "lucide-react";
import { Box } from "lucide-react";
import { resolveIconPath } from "~/lib/iconUtils";
import type { Workflow } from "~/types/api";

type MarketplaceCategory = "all" | TemplateCategory;

type SortOption = "newest" | "oldest" | "alphabetical" | "popular";

type FilterableItem = {
  name?: string | null;
  description?: string | null;
  category?: TemplateCategory;
  popularity?: number;
  created_at?: string;
  flow_data?: { nodes?: Array<{ type?: string }> } | null;
};

function getNodeTypes(item: FilterableItem): string {
  return (
    item.flow_data?.nodes
      ?.map((node) => node.type || "")
      .filter(Boolean)
      .join(" ")
      .toLowerCase() || ""
  );
}

function getSearchHaystack(item: FilterableItem): string {
  return `${item.name || ""} ${item.description || ""} ${getNodeTypes(item)}`.toLowerCase();
}

function matchesSearch(item: FilterableItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return getSearchHaystack(item).includes(q);
}

/** Infer categories from node types only (no loose description keywords). */
function inferCategoriesFromNodes(item: FilterableItem): TemplateCategory[] {
  const types = getNodeTypes(item);
  const cats: TemplateCategory[] = [];

  if (
    /kafkaconsumer|kafkaproducer|webhooktrigger|timerstart|errortrigger/.test(
      types
    )
  ) {
    cats.push("automation");
  }
  if (
    /chunksplitter|webscraper|vectorstore|documentloader|retriever|jsonparser/.test(
      types
    )
  ) {
    cats.push("data-processing");
  }
  if (
    /agent|openaichat|openaicompatible|openaiembeddings|coherereranker|buffermemory/.test(
      types
    )
  ) {
    cats.push("ai-ml");
  }
  if (/httprequest|webhooktrigger|respondtowebhook|kafkaconsumer|kafkaproducer/.test(types)) {
    cats.push("integration");
  }

  return cats;
}

function matchesCategory(
  item: FilterableItem,
  category: MarketplaceCategory
): boolean {
  if (category === "all") return true;
  // Templates have an explicit primary category
  if (item.category) return item.category === category;
  // Public workflows: match by node types
  return inferCategoriesFromNodes(item).includes(category);
}

function getPopularity(item: FilterableItem): number {
  if (typeof item.popularity === "number") return item.popularity;
  // No backend popularity yet — use node count as a richness proxy
  return item.flow_data?.nodes?.length ?? 0;
}

function getCreatedAtMs(item: FilterableItem): number {
  if (!item.created_at) return 0;
  const ms = new Date(item.created_at).getTime();
  return Number.isNaN(ms) ? 0 : ms;
}

function sortMarketplaceItems<T extends FilterableItem>(
  items: T[],
  sortBy: SortOption
): T[] {
  return [...items].sort((a, b) => {
    switch (sortBy) {
      case "oldest":
        return getCreatedAtMs(a) - getCreatedAtMs(b);
      case "alphabetical":
        return (a.name || "").localeCompare(b.name || "");
      case "popular":
        return getPopularity(b) - getPopularity(a);
      case "newest":
      default:
        return getCreatedAtMs(b) - getCreatedAtMs(a);
    }
  });
}

function MarketplaceLayout() {
  const { enqueueSnackbar } = useSnackbar();
  const {
    publicWorkflows,
    fetchPublicWorkflows,
    duplicateWorkflow,
    isLoading,
    error,
  } = useWorkflows();
  const { getPinnedItems } = usePinnedItems();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState("");
  const [duplicating, setDuplicating] = useState<string | null>(null);
  const [usingTemplateId, setUsingTemplateId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<MarketplaceCategory>("all");
  const [sortBy, setSortBy] = useState<SortOption>("newest");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  const itemsPerPage = 12;

  const filteredTemplates = useMemo(() => {
    const filtered = prebuiltTemplates.filter(
      (tpl) => matchesSearch(tpl, searchQuery) && matchesCategory(tpl, category)
    );
    return sortMarketplaceItems(filtered, sortBy);
  }, [searchQuery, category, sortBy]);

  const filteredWorkflows = useMemo(() => {
    if (!publicWorkflows?.length) return [];

    const filtered = publicWorkflows.filter(
      (workflow) =>
        matchesSearch(workflow, searchQuery) &&
        matchesCategory(workflow, category)
    );
    return sortMarketplaceItems(filtered, sortBy);
  }, [publicWorkflows, searchQuery, category, sortBy]);

  const totalItems = filteredWorkflows.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
  const startIdx = (page - 1) * itemsPerPage;
  const endIdx = Math.min(startIdx + itemsPerPage, totalItems);
  const pagedWorkflows = useMemo(
    () => filteredWorkflows.slice(startIdx, endIdx),
    [filteredWorkflows, startIdx, endIdx]
  );

  const totalResults = filteredTemplates.length + filteredWorkflows.length;
  const showInitialLoading =
    isLoading && !hasLoadedOnce && publicWorkflows.length === 0;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await fetchPublicWorkflows();
      } catch {
        // Error is already stored in the workflows store
      } finally {
        if (!cancelled) setHasLoadedOnce(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchPublicWorkflows]);

  useEffect(() => {
    setPage(1);
  }, [searchQuery, category, sortBy]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await fetchPublicWorkflows();
      enqueueSnackbar("Workflows refreshed!", {
        variant: "success",
        autoHideDuration: 2000,
      });
    } catch {
      enqueueSnackbar("Failed to refresh workflows", {
        variant: "error",
        autoHideDuration: 3000,
      });
    } finally {
      setIsRefreshing(false);
      setHasLoadedOnce(true);
    }
  }, [fetchPublicWorkflows, enqueueSnackbar]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const handleDuplicate = async (id: string) => {
    setDuplicating(id);
    try {
      await duplicateWorkflow(id);
      enqueueSnackbar("Workflow başarıyla kopyalandı!", {
        variant: "success",
        autoHideDuration: 3000,
      });
    } catch (e: any) {
      console.error("Duplicate error:", e);
      enqueueSnackbar("Workflow kopyalanamadı!", {
        variant: "error",
        autoHideDuration: 4000,
      });
    } finally {
      setDuplicating(null);
    }
  };

  const handleUseTemplate = async (tplId: string) => {
    if (usingTemplateId) return;

    const tpl = prebuiltTemplates.find((t) => t.id === tplId);
    if (!tpl) return;

    setUsingTemplateId(tplId);
    try {
      const created = await useWorkflows.getState().createWorkflow({
        name: tpl.name,
        description: tpl.description,
        flow_data: tpl.flow_data,
      });
      enqueueSnackbar("Template workflow created!", { variant: "success" });
      navigate(`/canvas?workflow=${created.id}`);
    } catch {
      enqueueSnackbar("Failed to create template workflow", {
        variant: "error",
      });
    } finally {
      setUsingTemplateId(null);
    }
  };

  const getIconComponent = (icon: {
    name: string;
    path: string | null;
    alt: string | null;
  }) => {
    if (icon?.path) {
      const iconPath = resolveIconPath(icon.path);
      return (props: any) => (
        <img
          src={iconPath}
          alt={icon.alt || ""}
          {...props}
          className={`${props.className || ""} object-contain`}
        />
      );
    }
    if (!icon?.name) return Box;

    let Icon = (LucideIcons as any)[icon.name];
    for (const [key, value] of Object.entries(LucideIcons)) {
      if (key.toLowerCase() === icon.name.replace(/-/g, "").toLowerCase()) {
        Icon = value;
        break;
      }
    }
    return Icon || Box;
  };

  const renderTemplateGrid = (templates: PrebuiltTemplate[]) => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {templates.map((tpl) => (
        <div
          key={tpl.id}
          className="group relative overflow-hidden rounded-2xl border border-gray-200 bg-white hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 hover:border-blue-200 hover:-translate-y-1"
        >
          <div className="absolute top-0 right-0 w-24 h-24 opacity-5">
            <div
              className={`w-full h-full bg-gradient-to-br ${tpl.colorFrom} ${tpl.colorTo} rounded-full transform translate-x-8 -translate-y-8`}
            />
          </div>

          <div className="relative p-6">
            <div className="flex items-center justify-between mb-4">
              <div
                className={`flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br ${tpl.colorFrom} ${tpl.colorTo} shadow-lg group-hover:scale-110 transition-transform duration-300`}
              >
                {React.createElement(getIconComponent(tpl.icon), {
                  className: "w-6 h-6 text-white",
                })}
              </div>
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full font-medium">
                Template
              </span>
            </div>

            <h3 className="text-lg font-bold text-gray-900 mb-2 group-hover:text-blue-700 transition-colors">
              {tpl.name}
            </h3>
            <p className="text-sm text-gray-600 mb-4 line-clamp-2 min-h-[40px]">
              {tpl.description}
            </p>

            <div className="flex flex-wrap gap-1 mb-4">
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-md">
                Ready-to-use
              </span>
              <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-md">
                Free
              </span>
            </div>

            <button
              type="button"
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl group-hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:group-hover:scale-100"
              onClick={() => handleUseTemplate(tpl.id)}
              disabled={usingTemplateId !== null}
            >
              <Download
                className={`w-4 h-4 ${usingTemplateId === tpl.id ? "animate-pulse" : ""}`}
              />
              {usingTemplateId === tpl.id ? "Creating..." : "Use Template"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );

  const renderTemplateTable = (templates: PrebuiltTemplate[]) => (
    <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white">
      <table className="w-full text-left">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">
              Name
            </th>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide hidden md:table-cell">
              Description
            </th>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">
              Type
            </th>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide text-right">
              Action
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {templates.map((tpl) => (
            <tr key={tpl.id} className="hover:bg-blue-50/40 transition-colors">
              <td className="px-4 py-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`flex items-center justify-center w-10 h-10 rounded-lg bg-gradient-to-br ${tpl.colorFrom} ${tpl.colorTo} shrink-0`}
                  >
                    {React.createElement(getIconComponent(tpl.icon), {
                      className: "w-5 h-5 text-white",
                    })}
                  </div>
                  <span className="font-semibold text-gray-900">{tpl.name}</span>
                </div>
              </td>
              <td className="px-4 py-4 text-sm text-gray-600 hidden md:table-cell max-w-md">
                <span className="line-clamp-2">{tpl.description}</span>
              </td>
              <td className="px-4 py-4">
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full font-medium">
                  Template
                </span>
              </td>
              <td className="px-4 py-4 text-right">
                <button
                  type="button"
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={() => handleUseTemplate(tpl.id)}
                  disabled={usingTemplateId !== null}
                >
                  <Download
                    className={`w-4 h-4 ${usingTemplateId === tpl.id ? "animate-pulse" : ""}`}
                  />
                  {usingTemplateId === tpl.id ? "Creating..." : "Use"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderWorkflowGrid = (workflows: Workflow[]) => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {workflows.map((wf) => (
        <div
          key={wf.id}
          className="group relative overflow-hidden rounded-2xl border border-gray-200 bg-white hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 hover:border-blue-200 hover:-translate-y-1"
        >
          <div className="absolute top-0 right-0 w-24 h-24 opacity-5">
            <div className="w-full h-full bg-gradient-to-br from-blue-500 to-green-500 rounded-full transform translate-x-8 -translate-y-8" />
          </div>

          <div className="relative p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-green-600 shadow-lg group-hover:scale-110 transition-transform duration-300">
                  <Users className="w-5 h-5 text-white" />
                </div>
                <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium w-fit">
                  Public
                </span>
              </div>
              <PinButton
                id={wf.id}
                type="workflow"
                title={wf.name}
                description={wf.description}
                metadata={{
                  status: "Public",
                  lastActivity: wf.created_at,
                }}
                size="sm"
                variant="minimal"
              />
            </div>

            <h3 className="text-lg font-bold text-gray-900 mb-2 group-hover:text-blue-700 transition-colors line-clamp-2">
              {wf.name}
            </h3>
            <p className="text-sm text-gray-600 mb-4 line-clamp-3 min-h-[60px]">
              {wf.description || "No description available"}
            </p>

            <div className="space-y-2 mb-4">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <Users className="w-3 h-3" />
                <span>
                  {wf.user?.full_name ||
                    `User ${wf.user_id?.slice(0, 8) || "Unknown"}...`}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <Clock className="w-3 h-3" />
                {timeAgo(wf.created_at)}
              </div>
            </div>

            <button
              type="button"
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-green-600 text-white hover:from-blue-700 hover:to-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl group-hover:scale-105"
              onClick={() => handleDuplicate(wf.id)}
              disabled={duplicating === wf.id}
            >
              <Copy
                className={`w-4 h-4 ${duplicating === wf.id ? "animate-spin" : ""}`}
              />
              {duplicating === wf.id ? "Copying..." : "Copy Workflow"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );

  const renderWorkflowTable = (workflows: Workflow[]) => (
    <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white">
      <table className="w-full text-left">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">
              Name
            </th>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide hidden lg:table-cell">
              Description
            </th>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide hidden md:table-cell">
              Author
            </th>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide hidden sm:table-cell">
              Created
            </th>
            <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide text-right">
              Action
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {workflows.map((wf) => (
            <tr key={wf.id} className="hover:bg-blue-50/40 transition-colors">
              <td className="px-4 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-green-600 shrink-0">
                    <Users className="w-5 h-5 text-white" />
                  </div>
                  <div className="min-w-0">
                    <div className="font-semibold text-gray-900 truncate">
                      {wf.name}
                    </div>
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                      Public
                    </span>
                  </div>
                  <PinButton
                    id={wf.id}
                    type="workflow"
                    title={wf.name}
                    description={wf.description}
                    metadata={{
                      status: "Public",
                      lastActivity: wf.created_at,
                    }}
                    size="sm"
                    variant="minimal"
                  />
                </div>
              </td>
              <td className="px-4 py-4 text-sm text-gray-600 hidden lg:table-cell max-w-sm">
                <span className="line-clamp-2">
                  {wf.description || "No description available"}
                </span>
              </td>
              <td className="px-4 py-4 text-sm text-gray-600 hidden md:table-cell">
                {wf.user?.full_name ||
                  `User ${wf.user_id?.slice(0, 8) || "Unknown"}...`}
              </td>
              <td className="px-4 py-4 text-sm text-gray-500 hidden sm:table-cell whitespace-nowrap">
                {timeAgo(wf.created_at)}
              </td>
              <td className="px-4 py-4 text-right">
                <button
                  type="button"
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-green-600 text-white hover:from-blue-700 hover:to-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  onClick={() => handleDuplicate(wf.id)}
                  disabled={duplicating === wf.id}
                >
                  <Copy
                    className={`w-4 h-4 ${duplicating === wf.id ? "animate-spin" : ""}`}
                  />
                  {duplicating === wf.id ? "Copying..." : "Copy"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="flex h-screen bg-background text-foreground">
      <DashboardSidebar />
      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <div className="flex flex-row items-end justify-between gap-6 mb-6">
                <div className="flex flex-col gap-1">
                  <h1 className="text-4xl font-bold text-blue-600">
                    Marketplace
                  </h1>
                  <p className="text-gray-600 text-lg">
                    Discover amazing workflows created by our community
                  </p>
                  <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
                    <span className="flex items-center gap-1">
                      <TrendingUp className="w-4 h-4" />
                      {searchQuery || category !== "all"
                        ? `${filteredWorkflows.length} of ${publicWorkflows.length} workflows`
                        : `${publicWorkflows.length} workflows available`}
                    </span>
                    <span className="flex items-center gap-1">
                      <Users className="w-4 h-4" />
                      Community driven
                    </span>
                  </div>
                </div>

                <div className="flex flex-col items-end gap-3">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      type="text"
                      className="pl-10 pr-4 py-2 w-64 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                      placeholder="Search workflows..."
                      value={searchQuery}
                      onChange={handleSearchChange}
                    />
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex items-center bg-gray-100 rounded-lg p-1">
                      <button
                        type="button"
                        aria-label="Grid view"
                        onClick={() => setViewMode("grid")}
                        className={`p-1.5 rounded-md transition-all duration-200 ${
                          viewMode === "grid"
                            ? "bg-white shadow-sm text-blue-600"
                            : "text-gray-600 hover:text-gray-800"
                        }`}
                      >
                        <Grid className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        aria-label="Table view"
                        onClick={() => setViewMode("list")}
                        className={`p-1.5 rounded-md transition-all duration-200 ${
                          viewMode === "list"
                            ? "bg-white shadow-sm text-blue-600"
                            : "text-gray-600 hover:text-gray-800"
                        }`}
                      >
                        <List className="w-4 h-4" />
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={handleRefresh}
                      disabled={isRefreshing}
                      className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <RefreshCw
                        className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`}
                      />
                      <span>{isRefreshing ? "Refreshing..." : "Refresh"}</span>
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex flex-row items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-200">
                <div className="flex flex-row items-center gap-3">
                  <span className="text-sm font-medium text-gray-700">
                    Filters:
                  </span>

                  <select
                    value={category}
                    onChange={(e) =>
                      setCategory(e.target.value as MarketplaceCategory)
                    }
                    className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="all">All Categories</option>
                    <option value="automation">Automation</option>
                    <option value="data-processing">Data Processing</option>
                    <option value="ai-ml">AI & ML</option>
                    <option value="integration">Integration</option>
                  </select>

                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as SortOption)}
                    className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="newest">Newest First</option>
                    <option value="oldest">Oldest First</option>
                    <option value="popular">Most Popular</option>
                    <option value="alphabetical">A-Z</option>
                  </select>

                  {(searchQuery ||
                    category !== "all" ||
                    sortBy !== "newest") && (
                    <button
                      type="button"
                      onClick={() => {
                        setSearchQuery("");
                        setCategory("all");
                        setSortBy("newest");
                      }}
                      className="px-3 py-2 text-sm text-gray-600 hover:text-gray-800 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      Clear All
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Filter className="w-4 h-4" />
                  {totalResults} results
                </div>
              </div>
            </div>

            {/* Pre-built Templates */}
            <div className="mb-10">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                    <Star className="w-4 h-4 text-white" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">
                      ⚡ Quick Start Templates
                    </h2>
                    <p className="text-sm text-gray-600">
                      Ready-to-use templates to get you started instantly
                    </p>
                  </div>
                </div>
                <span className="px-3 py-1 bg-blue-100 text-blue-700 text-xs font-semibold rounded-full">
                  {filteredTemplates.length} Templates
                </span>
              </div>

              {filteredTemplates.length === 0 ? (
                <div className="text-center py-8 text-gray-500 border border-dashed border-gray-200 rounded-2xl">
                  No templates match your current search or filters.
                </div>
              ) : viewMode === "grid" ? (
                renderTemplateGrid(filteredTemplates)
              ) : (
                renderTemplateTable(filteredTemplates)
              )}
            </div>

            {/* Pinned Workflows Section */}
            {(() => {
              const pinnedWorkflows = getPinnedItems("workflow");
              if (pinnedWorkflows.length > 0) {
                return (
                  <div className="mb-6">
                    <div className="flex items-center gap-2 mb-4">
                      <span className="text-lg font-semibold text-gray-900">
                        Your Pinned Workflows
                      </span>
                      <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-700 rounded-full">
                        {pinnedWorkflows.length}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {pinnedWorkflows.map((wf) => (
                        <div
                          key={wf.id}
                          className="bg-gradient-to-br from-red-50 to-pink-50 border-2 border-red-200 rounded-2xl p-6 hover:shadow-lg transition-all duration-300"
                        >
                          <div className="flex justify-between mb-4">
                            <h3 className="text-lg font-semibold text-gray-900">
                              {wf.title}
                            </h3>
                            <PinButton
                              id={wf.id}
                              type="workflow"
                              title={wf.title}
                              description={wf.description}
                              metadata={wf.metadata}
                              size="sm"
                              variant="minimal"
                            />
                          </div>
                          <p className="text-gray-600 text-sm mb-4">
                            {wf.description || "No description available"}
                          </p>
                          <div className="text-xs text-gray-500 space-y-1 mb-4">
                            <div>
                              <strong>Pinned:</strong> {timeAgo(wf.pinnedAt)}
                            </div>
                          </div>
                          <div className="flex justify-end pt-4 border-t border-red-100">
                            <button
                              type="button"
                              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-red-600 to-pink-600 text-white rounded-xl hover:from-red-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed"
                              onClick={() => handleDuplicate(wf.id)}
                              disabled={duplicating === wf.id}
                            >
                              <Copy
                                className={`w-4 h-4 ${duplicating === wf.id ? "animate-spin" : ""}`}
                              />
                              {duplicating === wf.id
                                ? "Copying..."
                                : "Copy Workflow"}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }
              return null;
            })()}

            {/* Public Workflows Section */}
            <div className="mb-10">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-gradient-to-r from-blue-600 to-green-600 rounded-lg flex items-center justify-center">
                    <Users className="w-4 h-4 text-white" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">
                      🌟 Community Workflows
                    </h2>
                    <p className="text-sm text-gray-600">
                      Workflows shared by our amazing community
                    </p>
                  </div>
                </div>
                <span className="px-3 py-1 bg-blue-100 text-blue-700 text-xs font-semibold rounded-full">
                  {filteredWorkflows.length} Public
                </span>
              </div>

              {showInitialLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loading size="sm" />
                </div>
              ) : error && publicWorkflows.length === 0 ? (
                <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-600">
                  {error}
                </div>
              ) : totalItems === 0 ? (
                <div className="flex flex-col items-center justify-center gap-6 py-12">
                  <div className="text-center">
                    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 mx-auto">
                      <Users className="w-8 h-8 text-gray-400" />
                    </div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">
                      No public workflows found
                    </h3>
                    <p className="text-gray-600 max-w-md">
                      {searchQuery || category !== "all"
                        ? `No workflows match your current search or filters. Try different keywords.`
                        : "There are no public workflows available at the moment. Check back later or be the first to share one!"}
                    </p>
                  </div>
                </div>
              ) : viewMode === "grid" ? (
                renderWorkflowGrid(pagedWorkflows)
              ) : (
                renderWorkflowTable(pagedWorkflows)
              )}
            </div>

            {!showInitialLoading && !error && filteredWorkflows.length > 0 && (
              <div className="mt-8">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-white rounded-2xl border border-gray-200">
                  <div className="text-sm text-gray-600">
                    Showing {totalItems === 0 ? 0 : startIdx + 1} to {endIdx} of{" "}
                    {totalItems} results
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setPage(page - 1)}
                      disabled={page === 1}
                      className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>

                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                      (p) => (
                        <button
                          type="button"
                          key={p}
                          onClick={() => setPage(p)}
                          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                            p === page
                              ? "bg-blue-600 text-white shadow-md"
                              : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
                          }`}
                        >
                          {p}
                        </button>
                      )
                    )}

                    <button
                      type="button"
                      onClick={() => setPage(page + 1)}
                      disabled={page === totalPages}
                      className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </div>

                  <div className="text-sm text-gray-600">
                    Page {page} of {totalPages}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function ProtectedMarketplaceLayout() {
  return (
    <AuthGuard>
      <MarketplaceLayout />
    </AuthGuard>
  );
}
