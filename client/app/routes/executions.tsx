import React, { useEffect, useState, useMemo } from "react";
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
} from "lucide-react";
import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import AuthGuard from "~/components/AuthGuard";
import Loading from "~/components/Loading";
import DeleteConfirmationModal from "~/components/modals/DeleteConfirmationModal";
import { useExecutionsStore } from "~/stores/executions";
import { useWorkflows } from "~/stores/workflows";
import { timeAgo } from "~/lib/dateFormatter";

interface Execution {
  id: string;
  workflow_id: string;
  status: "pending" | "running" | "completed" | "failed";
  input_text?: string;
  output_text?: string;
  started_at: string;
  completed_at?: string;
  error_message?: string;
}

function ExecutionsPage() {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
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

  // Multi-select states
  const [selectedExecutions, setSelectedExecutions] = useState<Set<string>>(
    new Set()
  );

  const { executions, loading, error, fetchAllExecutions, deleteExecution } =
    useExecutionsStore();
  const { workflows, fetchWorkflows } = useWorkflows();

  useEffect(() => {
    fetchWorkflows();
    fetchAllExecutions(); // Tüm executions'ları getir
  }, [fetchWorkflows, fetchAllExecutions]);

  // Filter executions
  const filteredExecutions = useMemo(() => {
    return executions.filter((execution) => {
      // Status filter
      if (filters.status !== "all" && execution.status !== filters.status) {
        return false;
      }

      // Workflow filter
      if (
        filters.workflowId !== "all" &&
        execution.workflow_id !== filters.workflowId
      ) {
        return false;
      }

      // Date range filter
      if (filters.dateRange !== "all" && execution.started_at) {
        const executionDate = new Date(execution.started_at);
        const now = new Date();
        const today = new Date(
          now.getFullYear(),
          now.getMonth(),
          now.getDate()
        );

        switch (filters.dateRange) {
          case "today":
            if (executionDate < today) return false;
            break;
          case "week":
            const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
            if (executionDate < weekAgo) return false;
            break;
          case "month":
            const monthAgo = new Date(
              today.getTime() - 30 * 24 * 60 * 60 * 1000
            );
            if (executionDate < monthAgo) return false;
            break;
        }
      }

      // Search filter
      if (filters.searchTerm) {
        const searchLower = filters.searchTerm.toLowerCase();
        const inputText = getInputText(execution).toLowerCase();
        const workflowName = getWorkflowName(
          execution.workflow_id
        ).toLowerCase();

        if (
          !inputText.includes(searchLower) &&
          !workflowName.includes(searchLower)
        ) {
          return false;
        }
      }

      return true;
    });
  }, [executions, filters, workflows]);

  const totalPages = Math.ceil(filteredExecutions.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const currentExecutions = filteredExecutions.slice(
    startIndex,
    startIndex + itemsPerPage
  );

  // Reset page and selections when filters change
  useEffect(() => {
    setCurrentPage(1);
    setSelectedExecutions(new Set());
  }, [filters]);

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
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getWorkflowName = (workflowId: string) => {
    const workflow = workflows.find((w) => w.id === workflowId);
    return workflow ? workflow.name : "Unknown Workflow";
  };

  const formatDuration = (startedAt: string, completedAt?: string) => {
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

  const getInputText = (execution: any) => {
    // String değerleri kontrol et
    if (execution.input_text && typeof execution.input_text === "string") {
      return execution.input_text;
    }

    // Eğer inputs objesi varsa, içindeki input değerini al
    if (execution.inputs && typeof execution.inputs === "object") {
      if (
        execution.inputs.input &&
        typeof execution.inputs.input === "string"
      ) {
        return execution.inputs.input;
      }
    }

    // Eğer input objesi varsa, içindeki değeri al
    if (execution.input) {
      if (typeof execution.input === "string") {
        return execution.input;
      } else if (typeof execution.input === "object" && execution.input.input) {
        return execution.input.input;
      }
    }

    return "No input provided";
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
    if (deleteModal.executionId === "bulk") {
      // Bulk delete
      const executionIds = Array.from(selectedExecutions);
      for (const id of executionIds) {
        await deleteExecution(id);
      }
      setSelectedExecutions(new Set());
    } else if (deleteModal.executionId) {
      // Single delete
      await deleteExecution(deleteModal.executionId);
    }

    setDeleteModal({
      isOpen: false,
      executionId: null,
    });
  };

  const handleDeleteCancel = () => {
    setDeleteModal({
      isOpen: false,
      executionId: null,
    });
  };

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const clearFilters = () => {
    setFilters({
      status: "all",
      workflowId: "all",
      searchTerm: "",
      dateRange: "all",
    });
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
    selectedCount > 0 && selectedCount === currentExecutions.length;
  const isPartiallySelected =
    selectedCount > 0 && selectedCount < currentExecutions.length;

  if (loading) {
    return (
      <div className="flex h-screen bg-background text-foreground">
        <DashboardSidebar />
        <main className="flex-1 flex items-center justify-center">
          <Loading size="lg" />
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background text-foreground">
      <DashboardSidebar />
      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
                <div>
                  <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                    Executions
                  </h1>
                  <p className="text-gray-600">
                    Monitor your workflow execution history
                  </p>
                </div>

                {/* Filter Controls */}
                <div className="flex flex-col sm:flex-row gap-3">
                  {/* Search */}
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search executions..."
                      className="pl-10 pr-4 py-2 w-64 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 text-sm"
                      value={filters.searchTerm}
                      onChange={(e) =>
                        handleFilterChange("searchTerm", e.target.value)
                      }
                    />
                  </div>

                  {/* Status Filter */}
                  <div className="relative">
                    <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <select
                      className="pl-10 pr-4 py-2 w-40 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 bg-white text-sm"
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
                  </div>

                  {/* Workflow Filter */}
                  <select
                    className="px-4 py-2 w-48 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 bg-white text-sm"
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

                  {/* Date Range Filter */}
                  <select
                    className="px-4 py-2 w-32 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 bg-white text-sm"
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

                  {/* Clear Filters */}
                  {hasActiveFilters && (
                    <button
                      onClick={clearFilters}
                      className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 bg-gray-100 hover:bg-gray-200 rounded-lg transition-all duration-200"
                      title="Clear all filters"
                    >
                      <RotateCcw className="w-4 h-4" />
                      Clear
                    </button>
                  )}
                </div>
              </div>

              {/* Bulk Actions */}
              {selectedCount > 0 && (
                <div className="flex items-center justify-between p-3 bg-purple-50 border border-purple-200 rounded-lg">
                  <span className="text-sm text-purple-700">
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
                  Showing {filteredExecutions.length} of {executions.length}{" "}
                  executions
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
                      Search: "{filters.searchTerm}"
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
            {filteredExecutions.length === 0 && !loading ? (
              <div className="text-center py-12">
                <Play className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-gray-600 mb-2">
                  {executions.length === 0
                    ? "No executions yet"
                    : "No results found"}
                </h3>
                <p className="text-gray-500">
                  {executions.length === 0
                    ? "Run a workflow to see execution history here"
                    : "Try adjusting your filters to see more results"}
                </p>
              </div>
            ) : (
              <>
                {/* Executions Table */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left">
                            <input
                              type="checkbox"
                              checked={isAllSelected}
                              ref={(el) => {
                                if (el) el.indeterminate = isPartiallySelected;
                              }}
                              onChange={(e) =>
                                handleSelectAll(e.target.checked)
                              }
                              className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                            />
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Workflow
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Status
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Started
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Duration
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Input
                          </th>
                          <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {currentExecutions.map((execution) => (
                          <tr key={execution.id} className="hover:bg-gray-50">
                            <td className="px-6 py-4">
                              <input
                                type="checkbox"
                                checked={selectedExecutions.has(execution.id)}
                                onChange={(e) =>
                                  handleSelectExecution(
                                    execution.id,
                                    e.target.checked
                                  )
                                }
                                className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                              />
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center">
                                <Play className="w-4 h-4 text-purple-600 mr-2" />
                                <div>
                                  <div className="text-sm font-medium text-gray-900">
                                    {getWorkflowName(execution.workflow_id)}
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    #{execution.id.slice(0, 8)}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-6 py-4">
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
                                {execution.status.charAt(0).toUpperCase() +
                                  execution.status.slice(1)}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-900">
                              {execution.started_at
                                ? timeAgo(execution.started_at)
                                : "-"}
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-900">
                              {formatDuration(
                                execution.started_at,
                                execution.completed_at
                              )}
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                              {getInputText(execution)}
                            </td>
                            <td className="px-6 py-4 text-right">
                              <button
                                onClick={() => handleDeleteClick(execution.id)}
                                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200"
                                title="Delete execution"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
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
                      {Math.min(
                        startIndex + itemsPerPage,
                        filteredExecutions.length
                      )}{" "}
                      of {filteredExecutions.length} executions
                      {hasActiveFilters && (
                        <span className="text-gray-500 ml-1">
                          (filtered from {executions.length} total)
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() =>
                          setCurrentPage((prev) => Math.max(prev - 1, 1))
                        }
                        disabled={currentPage === 1}
                        className="p-2 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronLeft className="w-5 h-5" />
                      </button>

                      <div className="flex gap-1">
                        {Array.from(
                          { length: totalPages },
                          (_, i) => i + 1
                        ).map((page) => (
                          <button
                            key={page}
                            onClick={() => setCurrentPage(page)}
                            className={`px-3 py-1 rounded text-sm ${page === currentPage
                              ? "bg-purple-600 text-white"
                              : "text-gray-700 hover:bg-gray-100"
                              }`}
                          >
                            {page}
                          </button>
                        ))}
                      </div>

                      <button
                        onClick={() =>
                          setCurrentPage((prev) =>
                            Math.min(prev + 1, totalPages)
                          )
                        }
                        disabled={currentPage === totalPages}
                        className="p-2 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
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
        isLoading={loading}
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
