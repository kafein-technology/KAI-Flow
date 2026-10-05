import React, { useEffect, useState, useMemo, useCallback, useRef } from "react";
import {
  Play,
  Clock,
  Check,
  X,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Filter,
  Search,
  RotateCcw,
  Download,
  Loader2,
  StopCircle,
} from "lucide-react";
import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import AuthGuard from "~/components/AuthGuard";
import Loading from "~/components/Loading";
import DeleteConfirmationModal from "~/components/modals/DeleteConfirmationModal";
import DataViewModal from "~/components/modals/DataViewModal";
import { timeAgo } from "~/lib/dateFormatter";
import {
  cancelExecution, deleteExecution, exportExecutionsCSV, getExecutionDetail,
  getExecutionPage, getExecutionWorkflowOptions,
  type ExecutionSummary,
} from "~/services/executionService";

const getErrorMessage = (error: unknown, fallback: string) => {
  if (typeof error === "object" && error !== null && "message" in error && typeof error.message === "string") {
    return error.message;
  }
  return fallback;
};

function ExecutionsPage() {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [workflows, setWorkflows] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMutating, setIsMutating] = useState(false);
  const requestController = useRef<AbortController | null>(null);
  const detailRequestId = useRef(0);
  const countedFilters = useRef<string | null>(null);
  const [deleteModal, setDeleteModal] = useState<{
    isOpen: boolean;
    executionId: string | null;
  }>({
    isOpen: false,
    executionId: null,
  });

  // Filter states
  const [filters, setFilters] = useState({
    status: "all",
    workflowId: "all",
    searchTerm: "",
    dateRange: "all", // all, today, week, month
  });
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(filters.searchTerm), 400);
    return () => clearTimeout(timer);
  }, [filters.searchTerm]);

  const startedAfter = useMemo(() => {
    if (filters.dateRange === "all") return undefined;
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    if (filters.dateRange === "week") date.setDate(date.getDate() - 7);
    if (filters.dateRange === "month") date.setTime(date.getTime() - 30 * 24 * 60 * 60 * 1000);
    return date.toISOString();
  }, [filters.dateRange]);

  const [viewModal, setViewModal] = useState<{
    isOpen: boolean;
    title: string;
    data: string | object | null;
  }>({
    isOpen: false,
    title: "",
    data: null,
  });

  const handleViewClick = async (executionId: string, field: "inputs" | "outputs") => {
    const requestId = ++detailRequestId.current;
    const title = field === "inputs" ? "Input Data" : "Output Data";
    setViewModal({ isOpen: true, title, data: "Loading..." });
    try {
      const detail = await getExecutionDetail(executionId);
      if (requestId === detailRequestId.current) {
        const value = detail[field];
        const data = typeof value === "object" && value !== null ? value : String(value ?? "No data");
        setViewModal({ isOpen: true, title, data });
      }
    } catch (e: unknown) {
      if (requestId === detailRequestId.current) {
        setViewModal({ isOpen: true, title, data: getErrorMessage(e, "Failed to load execution data") });
      }
    }
  };

  // Column resize state
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({
    workflow: 180,
    status: 120,
    started: 120,
    duration: 100,
    input: 250,
    output: 250,
  });

  const handleColumnResize = useCallback(
    (columnKey: string, startX: number, startWidth: number) => {
      const onMouseMove = (e: MouseEvent) => {
        const diff = e.clientX - startX;
        const newWidth = Math.max(80, startWidth + diff);
        setColumnWidths((prev) => ({ ...prev, [columnKey]: newWidth }));
      };
      const onMouseUp = () => {
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    },
    []
  );

  // Multi-select states
  const [selectedExecutions, setSelectedExecutions] = useState<Set<string>>(
    new Set()
  );

  const getWorkflowName = (workflowId: string) => {
    const workflow = workflows.find((w) => w.id === workflowId);
    return workflow ? workflow.name : "Unknown Workflow";
  };

  useEffect(() => {
    let mounted = true;
    getExecutionWorkflowOptions()
      .then((options) => { if (mounted) setWorkflows(options); })
      .catch((e: unknown) => { if (mounted) setError(getErrorMessage(e, "Failed to load workflows")); });
    return () => { mounted = false; };
  }, []);

  const loadPage = useCallback(async (silent = false, includeTotal?: boolean) => {
    if (silent && (document.hidden || requestController.current)) return;
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    const filterKey = JSON.stringify([filters.workflowId, filters.status, startedAfter, debouncedSearch.trim()]);
    const shouldCount = includeTotal ?? countedFilters.current !== filterKey;
    if (!silent) {
      setLoading(true);
      setError(null);
      setExecutions([]);
    }
    try {
      const result = await getExecutionPage({
        page: currentPage,
        workflow_id: filters.workflowId !== "all" ? filters.workflowId : undefined,
        status_filter: filters.status !== "all" ? filters.status : undefined,
        started_after: startedAfter,
        search: debouncedSearch.trim() || undefined,
        include_total: shouldCount,
      }, controller.signal);
      if (controller.signal.aborted) return;
      if (result.total !== null && currentPage > Math.max(1, Math.ceil(result.total / itemsPerPage))) {
        setTotal(result.total);
        setCurrentPage(Math.max(1, Math.ceil(result.total / itemsPerPage)));
        return;
      }
      setExecutions(result.items);
      if (result.total !== null) {
        setTotal(result.total);
        countedFilters.current = filterKey;
      }
    } catch (e: unknown) {
      if (!controller.signal.aborted) setError(getErrorMessage(e, "Failed to load executions"));
    } finally {
      if (requestController.current === controller) {
        requestController.current = null;
        setLoading(false);
      }
    }
  }, [currentPage, filters.workflowId, filters.status, startedAfter, debouncedSearch]);

  useEffect(() => {
    if (filters.searchTerm !== debouncedSearch) return;
    let active = true;
    queueMicrotask(() => { if (active) void loadPage(); });
    return () => {
      active = false;
      const controller = requestController.current;
      requestController.current = null;
      controller?.abort();
    };
  }, [loadPage, filters.searchTerm, debouncedSearch]);

  useEffect(() => {
    const timer = setInterval(() => { void loadPage(true, true); }, 30000);
    return () => clearInterval(timer);
  }, [loadPage]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) void loadPage(true, true);
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [loadPage]);

  const hasActiveExecution = executions.some(
    (ex) => ex.status === "running" || ex.status === "pending"
  );
  useEffect(() => {
    if (!hasActiveExecution) return;
    const timer = setInterval(() => { void loadPage(true, filters.status !== "all"); }, 5000);
    return () => clearInterval(timer);
  }, [hasActiveExecution, loadPage, filters.status]);

  // Listen for executions started from other tabs or widgets dynamically
  useEffect(() => {
    if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") return;

    const channel = new BroadcastChannel("kai-flow-executions");
    const handleMessage = (event: MessageEvent) => {
      if (event.data && event.data.type === "EXECUTION_STARTED") {
        void loadPage(true, true);
      }
    };
    channel.addEventListener("message", handleMessage);

    const handleLocalMessage = () => {
      void loadPage(true, true);
    };
    window.addEventListener("kai-flow-execution-started", handleLocalMessage);

    return () => {
      channel.removeEventListener("message", handleMessage);
      channel.close();
      window.removeEventListener("kai-flow-execution-started", handleLocalMessage);
    };
  }, [loadPage]);

  const totalPages = Math.max(1, Math.ceil(total / itemsPerPage));
  const startIndex = (currentPage - 1) * itemsPerPage;
  const currentExecutions = executions;
  const visiblePages = useMemo(() => {
    const pages = new Set([1, totalPages]);
    for (let page = Math.max(1, currentPage - 2); page <= Math.min(totalPages, currentPage + 2); page++) {
      pages.add(page);
    }
    return [...pages].sort((a, b) => a - b);
  }, [currentPage, totalPages]);

  const changePage = (page: number) => {
    setSelectedExecutions(new Set());
    setCurrentPage(page);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800 border-green-200";
      case "failed":
        return "bg-red-100 text-red-800 border-red-200";
      case "running":
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "pending":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "cancelled":
        return "bg-orange-100 text-orange-800 border-orange-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };



  const formatDuration = (startedAt: string | null, completedAt?: string | null) => {
    if (!startedAt) return "-";
    if (!completedAt) return "Running...";

    const start = new Date(startedAt);
    const end = new Date(completedAt);
    const duration = end.getTime() - start.getTime();

    if (duration < 60000) {
      return `${(duration / 1000).toFixed(2)} s`;
    }

    const minutes = Math.floor(duration / 60000);
    const remainingMs = duration % 60000;
    const seconds = (remainingMs / 1000).toFixed(2);
    return `${minutes}m ${seconds} s`;
  };



  const handleDeleteClick = (executionId: string) => {
    setDeleteModal({
      isOpen: true,
      executionId,
    });
  };

  const handleBulkDeleteClick = () => {
    if (selectedExecutions.size > 0) {
      setDeleteModal({
        isOpen: true,
        executionId: "bulk", // Special value for bulk delete
      });
    }
  };

  const handleDeleteConfirm = async () => {
    setIsMutating(true);
    try {
      if (deleteModal.executionId === "bulk") {
        for (const id of selectedExecutions) {
          await deleteExecution(id);
        }
      } else if (deleteModal.executionId) {
        await deleteExecution(deleteModal.executionId);
      }
      setSelectedExecutions(new Set());
      setDeleteModal({ isOpen: false, executionId: null });
      await loadPage(false, true);
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Failed to delete execution"));
    } finally {
      setIsMutating(false);
    }
  };

  const handleCancelExecution = async (executionId: string) => {
    if (!confirm("Are you sure you want to cancel this execution?")) return;
    setIsMutating(true);
    try {
      await cancelExecution(executionId);
      await loadPage(false, true);
    } catch (e: unknown) {
      setError(getErrorMessage(e, "Failed to cancel execution"));
    } finally {
      setIsMutating(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteModal({
      isOpen: false,
      executionId: null,
    });
  };

  const handleFilterChange = (key: string, value: string) => {
    setCurrentPage(1);
    setSelectedExecutions(new Set());
    setFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const clearFilters = () => {
    setCurrentPage(1);
    setSelectedExecutions(new Set());
    setFilters({
      status: "all",
      workflowId: "all",
      searchTerm: "",
      dateRange: "all",
    });
  };

  // CSV Export
  const [isExporting, setIsExporting] = useState(false);

  const handleExportCSV = async () => {
    try {
      setIsExporting(true);
      const hasSelected = selectedExecutions.size > 0;
      const { blob, filename } = await exportExecutionsCSV({
        // If checkboxes are selected, send their IDs; filters still sent for filename + safety
        execution_ids: hasSelected ? Array.from(selectedExecutions) : undefined,
        status_filter: filters.status !== "all" ? filters.status : undefined,
        workflow_id: filters.workflowId !== "all" ? filters.workflowId : undefined,
        date_range: filters.dateRange !== "all" ? filters.dateRange : undefined,
        // Always pass filter info for filename (even when checkbox is used)
        workflow_name: filters.workflowId !== "all" ? getWorkflowName(filters.workflowId) : undefined,
        search: filters.searchTerm.trim() || undefined,
        started_after: startedAfter,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("CSV export failed:", error);
    } finally {
      setIsExporting(false);
    }
  };

  const hasActiveFilters =
    filters.status !== "all" ||
    filters.workflowId !== "all" ||
    filters.searchTerm !== "" ||
    filters.dateRange !== "all";

  // Multi-select handlers
  const handleSelectExecution = (executionId: string, checked: boolean) => {
    setSelectedExecutions((prev) => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(executionId);
      } else {
        newSet.delete(executionId);
      }
      return newSet;
    });
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allIds = new Set(currentExecutions.map((ex) => ex.id));
      setSelectedExecutions(allIds);
    } else {
      setSelectedExecutions(new Set());
    }
  };

  const selectedCount = selectedExecutions.size;
  const isAllSelected =
    currentExecutions.length > 0 && currentExecutions.every((ex) => selectedExecutions.has(ex.id));
  const isPartiallySelected =
    currentExecutions.some((ex) => selectedExecutions.has(ex.id)) && !isAllSelected;

  return (
    <div className="flex h-screen bg-background text-foreground">
      <DashboardSidebar />
      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto [scrollbar-gutter:stable] p-6">
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <div className="flex flex-col gap-4">
                <div>
                  <h1 className="text-4xl font-bold text-blue-600">
                    Executions
                  </h1>
                  <p className="text-gray-600">
                    Monitor your workflow execution history
                  </p>
                </div>

                {/* Filter Controls */}
                <div className="flex flex-wrap items-center gap-3">
                  {/* Search */}
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search executions..."
                      maxLength={200}
                      className="pl-10 pr-4 py-2 w-64 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-sm"
                      value={filters.searchTerm}
                      onChange={(e) =>
                        handleFilterChange("searchTerm", e.target.value)
                      }
                    />
                  </div>

                  {/* Status Filter */}
                  <div className="relative">
                    <select
                      className="pl-4 pr-10 py-2 w-40 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-white text-sm appearance-none"
                      value={filters.status}
                      onChange={(e) =>
                        handleFilterChange("status", e.target.value)
                      }
                    >
                      <option value="all">All Status</option>
                      <option value="completed">Completed</option>
                      <option value="failed">Failed</option>
                      <option value="running">Running</option>
                      <option value="pending">Pending</option>
                    </select>
                    <Filter className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  </div>

                  {/* Workflow Filter */}
                  <div className="relative">
                    <select
                      className="pl-4 pr-10 py-2 w-48 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-white text-sm appearance-none"
                      value={filters.workflowId}
                      onChange={(e) =>
                        handleFilterChange("workflowId", e.target.value)
                      }
                    >
                      <option value="all">All Workflows</option>
                      {workflows.map((workflow) => (
                        <option key={workflow.id} value={workflow.id}>
                          {workflow.name}
                        </option>
                      ))}
                    </select>
                    <Filter className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  </div>

                  {/* Date Range Filter */}
                  <div className="relative">
                    <select
                      className="pl-4 pr-10 py-2 w-40 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-white text-sm appearance-none"
                      value={filters.dateRange}
                      onChange={(e) =>
                        handleFilterChange("dateRange", e.target.value)
                      }
                    >
                      <option value="all">All Time</option>
                      <option value="today">Today</option>
                      <option value="week">Last Week</option>
                      <option value="month">Last Month</option>
                    </select>
                    <Filter className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  </div>

                  {/* Export CSV */}
                  <button
                    onClick={handleExportCSV}
                    disabled={isExporting || total === 0}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-all duration-200 whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Export filtered executions as CSV"
                  >
                    {isExporting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Preparing CSV...
                      </>
                    ) : (
                      <>
                        <Download className="w-4 h-4" />
                        Export CSV
                      </>
                    )}
                  </button>

                  {/* Clear Filters */}
                  <button
                    onClick={clearFilters}
                    disabled={!hasActiveFilters}
                    aria-hidden={!hasActiveFilters}
                    tabIndex={hasActiveFilters ? 0 : -1}
                    className={`flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 bg-gray-100 hover:bg-gray-200 rounded-lg transition-all duration-200 whitespace-nowrap ${hasActiveFilters ? "" : "invisible"}`}
                    title="Clear all filters"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Clear
                  </button>
                </div>
              </div>

              {/* Bulk Actions */}
              {selectedCount > 0 && (
                <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <span className="text-sm text-blue-700">
                    {selectedCount} execution{selectedCount > 1 ? "s" : ""}{" "}
                    selected
                  </span>
                  <button
                    onClick={handleBulkDeleteClick}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm text-red-700 bg-red-100 hover:bg-red-200 rounded-md transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete Selected
                  </button>
                </div>
              )}
            </div>

            {/* Error State */}
            {error && (
              <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-800">
                  {typeof error === "string"
                    ? error
                    : "An error occurred while loading executions"}
                </p>
              </div>
            )}

            {/* Filter Results Info */}
            {hasActiveFilters && !loading && (
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-700">
                  <Filter className="inline w-4 h-4 mr-1" />
                  {total} matching executions
                  {filters.status !== "all" && (
                    <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-md">
                      Status: {filters.status}
                    </span>
                  )}
                  {filters.workflowId !== "all" && (
                    <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-md">
                      Workflow: {getWorkflowName(filters.workflowId)}
                    </span>
                  )}
                  {filters.searchTerm && (
                    <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-md">
                      Search: &quot;{filters.searchTerm}&quot;
                    </span>
                  )}
                  {filters.dateRange !== "all" && (
                    <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-md">
                      Date:{" "}
                      {filters.dateRange === "today"
                        ? "Today"
                        : filters.dateRange === "week"
                          ? "Last Week"
                          : "Last Month"}
                    </span>
                  )}
                </p>
              </div>
            )}

            {/* Empty State */}
            {loading ? (
              <div className="flex min-h-[240px] items-center justify-center" role="status" aria-label="Loading executions">
                <Loading size="lg" />
              </div>
            ) : executions.length === 0 && !error ? (
              <div className="text-center py-12">
                <Play className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-gray-600 mb-2">
                  {total === 0 && !hasActiveFilters
                    ? "No executions yet"
                    : "No results found"}
                </h3>
                <p className="text-gray-500">
                  {total === 0 && !hasActiveFilters
                    ? "Run a workflow to see execution history here"
                    : "Try adjusting your filters to see more results"}
                </p>
              </div>
            ) : (
              <>
                {/* Executions Table */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden min-h-[921px]">
                  <div className="overflow-x-auto">
                    <table className="w-full" style={{ tableLayout: "fixed" }}>
                      <colgroup>
                        <col style={{ width: 40 }} />
                        <col style={{ width: columnWidths.workflow }} />
                        <col style={{ width: columnWidths.status }} />
                        <col style={{ width: columnWidths.started }} />
                        <col style={{ width: columnWidths.duration }} />
                        <col style={{ width: columnWidths.input }} />
                        <col style={{ width: columnWidths.output }} />
                        <col style={{ width: 110 }} />
                      </colgroup>
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-3 text-left border-r border-gray-200">
                            <input
                              type="checkbox"
                              checked={isAllSelected}
                              ref={(el) => {
                                if (el) el.indeterminate = isPartiallySelected;
                              }}
                              onChange={(e) =>
                                handleSelectAll(e.target.checked)
                              }
                              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                          </th>
                          {(
                            [
                              ["workflow", "Workflow"],
                              ["status", "Status"],
                              ["started", "Started"],
                              ["duration", "Duration"],
                              ["input", "Input"],
                              ["output", "Output"],
                            ] as const
                          ).map(([key, label]) => (
                            <th
                              key={key}
                              className="relative px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider select-none border-r border-gray-200"
                            >
                              {label}
                              <div
                                className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-blue-400 active:bg-blue-500 transition-colors"
                                onMouseDown={(e) => {
                                  e.preventDefault();
                                  handleColumnResize(
                                    key,
                                    e.clientX,
                                    columnWidths[key]
                                  );
                                }}
                              />
                            </th>
                          ))}
                          <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {currentExecutions.map((execution) => (
                          <tr key={execution.id} className="hover:bg-gray-50 h-[88px]">
                            <td className="px-3 py-4 align-top">
                              <input
                                type="checkbox"
                                checked={selectedExecutions.has(execution.id)}
                                onChange={(e) =>
                                  handleSelectExecution(
                                    execution.id,
                                    e.target.checked
                                  )
                                }
                                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 mt-0.5"
                              />
                            </td>
                            <td className="px-3 py-4 align-top">
                              <div className="flex items-start">
                                <Play className="w-4 h-4 text-blue-600 mr-2 flex-shrink-0 mt-0.5" />
                                <div className="min-w-0 flex-1">
                                  <div
                                    className="text-sm font-medium text-gray-900 line-clamp-2 h-10"
                                    title={execution.workflow_name}
                                  >
                                    {execution.workflow_name}
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    #{execution.id.slice(0, 8)}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-4 align-top">
                              <div className="truncate pt-0.5">
                                <span
                                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(
                                    execution.status
                                  )}`}
                                >
                                  {execution.status === "completed" && (
                                    <Check className="w-3 h-3 mr-1" />
                                  )}
                                  {execution.status === "failed" && (
                                    <X className="w-3 h-3 mr-1" />
                                  )}
                                  {execution.status === "running" && (
                                    <Clock className="w-3 h-3 mr-1 animate-spin" />
                                  )}
                                  {execution.status === "cancelled" && (
                                    <X className="w-3 h-3 mr-1" />
                                  )}
                                  {execution.status.charAt(0).toUpperCase() +
                                    execution.status.slice(1)}
                                </span>
                              </div>
                            </td>
                            <td className="px-3 py-4 text-sm text-gray-900 align-top">
                              <div className="line-clamp-2 h-10 pt-0.5" title={execution.started_at ? timeAgo(execution.started_at) : "-"}>
                                {execution.started_at
                                  ? timeAgo(execution.started_at)
                                  : "-"}
                              </div>
                            </td>
                            <td className="px-3 py-4 text-sm text-gray-900 align-top">
                              <div className="truncate pt-0.5" title={formatDuration(execution.started_at, execution.completed_at)}>
                                {formatDuration(
                                  execution.started_at,
                                  execution.completed_at
                                )}
                              </div>
                            </td>
                            <td className="px-3 py-4 text-sm align-top">
                              {execution.has_inputs ? (
                                <button className="text-blue-600 hover:underline" onClick={() => handleViewClick(execution.id, "inputs")}>View input</button>
                              ) : "-"}
                            </td>
                            <td className="px-3 py-4 text-sm align-top">
                              {execution.has_outputs ? (
                                <button className="text-blue-600 hover:underline" onClick={() => handleViewClick(execution.id, "outputs")}>View output</button>
                              ) : "-"}
                            </td>
                            <td className="px-3 py-4 text-center align-top">
                              <div className="flex justify-center items-start gap-2.5 pt-0.5">
                                {(execution.status === "running" || execution.status === "pending") && (
                                  <button
                                    onClick={() => handleCancelExecution(execution.id)}
                                    disabled={isMutating}
                                    className="p-1.5 text-gray-400 hover:text-orange-500 hover:bg-orange-50 rounded-lg transition-all duration-200"
                                    title="Cancel execution"
                                  >
                                    <StopCircle className="w-4 h-4" />
                                  </button>
                                )}
                                <button
                                  onClick={() => handleDeleteClick(execution.id)}
                                  disabled={isMutating}
                                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200"
                                  title="Delete execution"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-6">
                    <div className="text-sm text-gray-700">
                      Showing {startIndex + 1} to{" "}
                      {Math.min(startIndex + currentExecutions.length, total)} of {total} executions
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => changePage(Math.max(currentPage - 1, 1))}
                        disabled={currentPage === 1}
                        className="p-2 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Previous page"
                      >
                        <ChevronLeft className="w-5 h-5" />
                      </button>
 
                      <div className="flex gap-1">
                        {visiblePages.map((page, index) => (
                          <React.Fragment key={page}>
                            {index > 0 && page - visiblePages[index - 1] > 1 && <span className="px-1 text-gray-500">...</span>}
                            <button
                              onClick={() => changePage(page)}
                              className={`px-3 py-1 rounded text-sm ${page === currentPage
                                ? "bg-blue-600 text-white"
                                : "text-gray-700 hover:bg-gray-100"
                                }`}
                            >
                              {page}
                            </button>
                          </React.Fragment>
                        ))}
                      </div>
 
                      <button
                        onClick={() => changePage(Math.min(currentPage + 1, totalPages))}
                        disabled={currentPage === totalPages}
                        className="p-2 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Next page"
                      >
                        <ChevronRight className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>

      {/* Delete Confirmation Modal */}
      <DeleteConfirmationModal
        isOpen={deleteModal.isOpen}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        isLoading={isMutating}
        title={
          deleteModal.executionId === "bulk"
            ? "Delete Multiple Executions"
            : "Delete Execution"
        }
        message={
          deleteModal.executionId === "bulk"
            ? `Are you sure you want to delete ${selectedCount} execution${selectedCount > 1 ? "s" : ""
            }? This action cannot be undone and all execution data will be permanently removed.`
            : "Are you sure you want to delete this execution? This action cannot be undone and all execution data will be permanently removed."
        }
        confirmText={
          deleteModal.executionId === "bulk"
            ? `Delete ${selectedCount} Executions`
            : "Delete"
        }
      />

      {/* Data View Modal */}
      <DataViewModal
        isOpen={viewModal.isOpen}
        onClose={() => {
          detailRequestId.current += 1;
          setViewModal((current) => ({ ...current, isOpen: false }));
        }}
        title={viewModal.title}
        data={viewModal.data}
      />
    </div>
  );
}

export default function ProtectedExecutionsPage() {
  return (
    <AuthGuard>
      <ExecutionsPage />
    </AuthGuard>
  );
}
