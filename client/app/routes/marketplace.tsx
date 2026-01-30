import React, { useEffect, useState } from "react";
import Icon, {
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
  Tag,
  Download,
  Grid,
  List,
  Box,
} from "~/components/common/Icon";
import { resolveIconPath } from "~/lib/iconUtils";
import { prebuiltTemplates } from "~/data/prebuiltTemplates";
import { useNavigate } from "react-router";
import { useSnackbar } from "notistack";
import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import { useWorkflows } from "~/stores/workflows";
import { usePinnedItems } from "~/stores/pinnedItems";
import { timeAgo } from "~/lib/dateFormatter";
import AuthGuard from "~/components/AuthGuard";
import Loading from "~/components/Loading";
import PinButton from "~/components/common/PinButton";

type IconComponent = React.ComponentType<{ className?: string; size?: number }>;

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
  const [itemsPerPage, setItemsPerPage] = useState(9);
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("all");
  const [sortBy, setSortBy] = useState("newest");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  const filteredWorkflows = publicWorkflows
    .filter((workflow) => {
      // Search filter
      const matchesSearch =
        searchQuery === "" ||
        workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        workflow.description?.toLowerCase().includes(searchQuery.toLowerCase());

      // Category filter - for now we'll just filter by name/description keywords
      // In a real implementation, workflows would have category metadata
      const matchesCategory =
        category === "all" ||
        (category === "automation" &&
          (workflow.name.toLowerCase().includes("automat") ||
            workflow.description?.toLowerCase().includes("automat"))) ||
        (category === "data-processing" &&
          (workflow.name.toLowerCase().includes("data") ||
            workflow.description?.toLowerCase().includes("data"))) ||
        (category === "ai-ml" &&
          (workflow.name.toLowerCase().includes("ai") ||
            workflow.name.toLowerCase().includes("ml") ||
            workflow.description?.toLowerCase().includes("ai"))) ||
        (category === "integration" &&
          (workflow.name.toLowerCase().includes("integrat") ||
            workflow.description?.toLowerCase().includes("integrat")));

      return matchesSearch && matchesCategory;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case "newest":
          return (
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
        case "oldest":
          return (
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          );
        case "alphabetical":
          return a.name.localeCompare(b.name);
        case "popular":
          // For now, sort by created date as we don't have popularity metrics
          return (
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
        default:
          return 0;
      }
    });

  const totalItems = filteredWorkflows.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
  const startIdx = (page - 1) * itemsPerPage;
  const endIdx = Math.min(startIdx + itemsPerPage, totalItems);
  const pagedWorkflows = filteredWorkflows.slice(startIdx, endIdx);

  useEffect(() => {
    fetchPublicWorkflows();
  }, [fetchPublicWorkflows]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [searchQuery, category, sortBy]);

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

  // Pre-built Templates

  const handleUseTemplate = async (tplId: string) => {
    const tpl = prebuiltTemplates.find((t) => t.id === tplId);
    if (!tpl) return;

    try {
      const created = await useWorkflows.getState().createWorkflow({
        name: tpl.name,
        description: tpl.description,
        flow_data: tpl.flow_data,
      });
      enqueueSnackbar("Template workflow created!", { variant: "success" });
      navigate(`/canvas?workflow=${created.id}`);
    } catch (e: any) {
      enqueueSnackbar("Failed to create template workflow", {
        variant: "error",
      });
    }
  };

  const getIconComponent = (icon: { name: string; path: string | null; alt: string | null } | undefined): IconComponent => {
    // Prioritize Icon component if name is available, as it handles path resolution correctly
    if (icon?.name) {
      return (props: any) => <Icon name={icon.name} {...props} />;
    }

    if (icon?.path) {
      const iconPath = resolveIconPath(icon.path);
      return (props: any) => (
        <img
          src={iconPath}
          alt={icon.alt}
          {...props}
          className={`${props.className || ""} object-contain`}
        />
      );
    }
    
    return Box;
  };

  return (
    <div className="flex h-screen bg-background text-foreground">
      <DashboardSidebar />
      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6 mb-6">
                <div>
                  <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                    Marketplace
                  </h1>
                  <p className="text-gray-600 text-lg">
                    Discover amazing workflows created by our community
                  </p>
                  <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                    <span className="flex items-center gap-1">
                      <TrendingUp className="w-4 h-4" />
                      {publicWorkflows.length} workflows available
                    </span>
                    <span className="flex items-center gap-1">
                      <Users className="w-4 h-4" />
                      Community driven
                    </span>
                  </div>
                </div>

                {/* Search and Controls */}
                <div className="flex flex-col gap-4">
                  <div className="relative w-full sm:w-auto">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      type="search"
                      className="pl-10 pr-4 py-2.5 w-full sm:w-72 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200"
                      placeholder="Search workflows, templates, or keywords..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>

                  <div className="flex items-center justify-between sm:justify-start gap-3">
                    {/* View Mode Toggle */}
                    <div className="flex items-center bg-gray-100 rounded-lg p-1">
                      <button
                        onClick={() => setViewMode("grid")}
                        className={`p-2 rounded-md transition-all duration-200 ${viewMode === "grid"
                          ? "bg-white shadow-sm text-purple-600"
                          : "text-gray-600 hover:text-gray-800"
                          }`}
                      >
                        <Grid className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setViewMode("list")}
                        className={`p-2 rounded-md transition-all duration-200 ${viewMode === "list"
                          ? "bg-white shadow-sm text-purple-600"
                          : "text-gray-600 hover:text-gray-800"
                          }`}
                      >
                        <List className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Refresh Button */}
                    <button
                      onClick={fetchPublicWorkflows}
                      className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl hover:from-purple-700 hover:to-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl"
                    >
                      <RefreshCw
                        className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
                      />
                      <span className="hidden sm:inline">Refresh</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Filters Row */}
              <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 p-4 bg-gray-50 rounded-xl border border-gray-200">
                <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-center gap-3 w-full lg:w-auto">
                  <span className="text-sm font-medium text-gray-700">
                    Filters:
                  </span>

                  <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                    {/* Category Filter */}
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-purple-500 focus:border-transparent w-full sm:w-auto"
                    >
                      <option value="all">All Categories</option>
                      <option value="automation">Automation</option>
                      <option value="data-processing">Data Processing</option>
                      <option value="ai-ml">AI & ML</option>
                      <option value="integration">Integration</option>
                    </select>

                    {/* Sort Filter */}
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value)}
                      className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-purple-500 focus:border-transparent w-full sm:w-auto"
                    >
                      <option value="newest">Newest First</option>
                      <option value="oldest">Oldest First</option>
                      <option value="popular">Most Popular</option>
                      <option value="alphabetical">A-Z</option>
                    </select>

                    {/* Clear Filters Button */}
                    {(searchQuery ||
                      category !== "all" ||
                      sortBy !== "newest") && (
                        <button
                          onClick={() => {
                            setSearchQuery("");
                            setCategory("all");
                            setSortBy("newest");
                          }}
                          className="px-3 py-2 text-sm text-gray-600 hover:text-gray-800 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors w-full sm:w-auto"
                        >
                          Clear All
                        </button>
                      )}
                  </div>
                </div>

                <div className="flex items-center justify-between w-full lg:w-auto">
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Filter className="w-4 h-4" />
                    {filteredWorkflows.length} results
                  </div>

                  {/* Items per page selector on mobile */}
                  <div className="flex items-center gap-2 lg:hidden">
                    <span className="text-sm text-gray-600">Show:</span>
                    <select
                      value={itemsPerPage}
                      onChange={(e) => setItemsPerPage(Number(e.target.value))}
                      className="px-2 py-1 text-sm border border-gray-300 rounded bg-white"
                    >
                      <option value={6}>6</option>
                      <option value={9}>9</option>
                      <option value={12}>12</option>
                      <option value={18}>18</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            {/* Pre-built Templates */}
            <div className="mb-10">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg flex items-center justify-center">
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
                <span className="px-3 py-1 bg-purple-100 text-purple-700 text-xs font-semibold rounded-full">
                  {prebuiltTemplates.length} Templates
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {prebuiltTemplates.map((tpl) => (
                  <div
                    key={tpl.id}
                    className="group relative overflow-hidden rounded-2xl border border-gray-200 bg-white hover:shadow-xl hover:shadow-purple-500/10 transition-all duration-300 hover:border-purple-200 hover:-translate-y-1"
                  >
                    {/* Background Pattern */}
                    <div className="absolute top-0 right-0 w-24 h-24 opacity-5">
                      <div
                        className={`w-full h-full bg-gradient-to-br ${tpl.colorFrom} ${tpl.colorTo} rounded-full transform translate-x-8 -translate-y-8`}
                      />
                    </div>

                    <div className="relative p-6">
                      {/* Icon */}
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

                      {/* Content */}
                      <h3 className="text-lg font-bold text-gray-900 mb-2 group-hover:text-purple-700 transition-colors">
                        {tpl.name}
                      </h3>
                      <p className="text-sm text-gray-600 mb-4 line-clamp-2 min-h-[40px]">
                        {tpl.description}
                      </p>

                      {/* Tags */}
                      <div className="flex flex-wrap gap-1 mb-4">
                        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-md">
                          Ready-to-use
                        </span>
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-md">
                          Free
                        </span>
                      </div>

                      {/* Action Button */}
                      <button
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl group-hover:scale-105"
                        onClick={() => handleUseTemplate(tpl.id)}
                      >
                        <Download className="w-4 h-4" />
                        Use Template
                      </button>
                    </div>
                  </div>
                ))}
              </div>
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
                            <button className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-red-600 to-pink-600 text-white rounded-xl hover:from-red-700 hover:to-pink-700">
                              <Copy className="w-4 h-4" />
                              Copy Workflow
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
                  {publicWorkflows.length} Public
                </span>
              </div>

              {/* Content */}
              {isLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loading size="sm" />
                </div>
              ) : error ? (
                <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-600">
                  {error}
                </div>
              ) : totalItems === 0 ? (
                <div className="flex flex-col items-center justify-center gap-6 py-12">
                  <div className="text-center">
                    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                      <Users className="w-8 h-8 text-gray-400" />
                    </div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">
                      No public workflows found
                    </h3>
                    <p className="text-gray-600 max-w-md">
                      {searchQuery
                        ? `No workflows match your search "${searchQuery}". Try different keywords.`
                        : "There are no public workflows available at the moment. Check back later or be the first to share one!"}
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  {viewMode === "grid" ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                      {pagedWorkflows.map((wf) => (
                        <div
                          key={wf.id}
                          className="group relative overflow-hidden rounded-2xl border border-gray-200 bg-white hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 hover:border-blue-200 hover:-translate-y-1"
                        >
                          {/* Background Pattern */}
                          <div className="absolute top-0 right-0 w-24 h-24 opacity-5">
                            <div className="w-full h-full bg-gradient-to-br from-blue-500 to-green-500 rounded-full transform translate-x-8 -translate-y-8" />
                          </div>

                          <div className="relative p-6">
                            {/* Header */}
                            <div className="flex items-start justify-between mb-4">
                              <div className="flex items-center gap-3">
                                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-green-600 shadow-lg group-hover:scale-110 transition-transform duration-300">
                                  <Users className="w-5 h-5 text-white" />
                                </div>
                                <div className="flex flex-col">
                                  <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium w-fit">
                                    Public
                                  </span>
                                </div>
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

                            {/* Content */}
                            <h3 className="text-lg font-bold text-gray-900 mb-2 group-hover:text-blue-700 transition-colors line-clamp-2">
                              {wf.name}
                            </h3>
                            <p className="text-sm text-gray-600 mb-4 line-clamp-3 min-h-[60px]">
                              {wf.description || "No description available"}
                            </p>

                            {/* Metadata */}
                            <div className="space-y-2 mb-4">
                              <div className="flex items-center gap-2 text-xs text-gray-500">
                                <Users className="w-3 h-3" />
                                <span>
                                  {wf.user?.full_name || `User ${wf.user_id?.slice(0, 8) || "Unknown"}...`}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-xs text-gray-500">
                                <Clock className="w-3 h-3" />
                                {timeAgo(wf.created_at)}
                              </div>
                            </div>

                            {/* Action Button */}
                            <button
                              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-green-600 text-white hover:from-blue-700 hover:to-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl group-hover:scale-105"
                              onClick={() => handleDuplicate(wf.id)}
                              disabled={duplicating === wf.id}
                            >
                              <Copy
                                className={`w-4 h-4 ${duplicating === wf.id ? "animate-spin" : ""
                                  }`}
                              />
                              {duplicating === wf.id
                                ? "Copying..."
                                : "Copy Workflow"}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {pagedWorkflows.map((wf) => (
                        <div
                          key={wf.id}
                          className="group flex items-center gap-6 p-6 bg-white border border-gray-200 rounded-2xl hover:shadow-lg hover:border-blue-200 transition-all duration-300"
                        >
                          {/* Icon */}
                          <div className="flex-shrink-0">
                            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-green-600 shadow-lg group-hover:scale-105 transition-transform duration-300">
                              <Users className="w-6 h-6 text-white" />
                            </div>
                          </div>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center gap-3">
                                <h3 className="text-lg font-bold text-gray-900 group-hover:text-blue-700 transition-colors">
                                  {wf.name}
                                </h3>
                                <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
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
                            <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                              {wf.description || "No description available"}
                            </p>
                            <div className="flex items-center gap-4 text-xs text-gray-500">
                              <div className="flex items-center gap-1">
                                <Users className="w-3 h-3" />
                                <span>
                                  {wf.user?.full_name || `User ${wf.user_id?.slice(0, 8) || "Unknown"}...`}
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {timeAgo(wf.created_at)}
                              </div>
                            </div>
                          </div>

                          {/* Action */}
                          <div className="flex-shrink-0">
                            <button
                              className="flex items-center gap-2 px-6 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-green-600 text-white hover:from-blue-700 hover:to-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl"
                              onClick={() => handleDuplicate(wf.id)}
                              disabled={duplicating === wf.id}
                            >
                              <Copy
                                className={`w-4 h-4 ${duplicating === wf.id ? "animate-spin" : ""
                                  }`}
                              />
                              {duplicating === wf.id
                                ? "Copying..."
                                : "Copy Workflow"}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Pagination */}
            {!isLoading && !error && publicWorkflows.length > 0 && (
              <div className="mt-8">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-white  rounded-2xl">
                  <div></div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage(page - 1)}
                      disabled={page === 1}
                      className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-50"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>

                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                      (p) => (
                        <button
                          key={p}
                          onClick={() => setPage(p)}
                          className={`px-4 py-2 rounded-lg text-sm border ${p === page
                            ? "bg-purple-600 text-white"
                            : "bg-white text-gray-700 border-gray-300"
                            }`}
                        >
                          {p}
                        </button>
                      )
                    )}

                    <button
                      onClick={() => setPage(page + 1)}
                      disabled={page === totalPages}
                      className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-50"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </div>

                  <div className="text-sm text-gray-600">
                    Items {totalItems === 0 ? 0 : startIdx + 1} to {endIdx} of{" "}
                    {totalItems}
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
