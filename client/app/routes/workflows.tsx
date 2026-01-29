import {
  Pencil,
  Plus,
  Search,
  Trash,
  AlertCircle,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  Play,
  Pause,
  Activity,
  Clock,
  Calendar,
  Globe,
  MessageCircle,
  Eye,
  X,
  Download,
} from "lucide-react";
import React, { useState, useEffect } from "react";

import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import { useWorkflows } from "~/stores/workflows";
import { usePinnedItems } from "~/stores/pinnedItems";
import CompactToggleSwitch from "~/components/common/ToggleSwitch";

import type {
  Workflow,
  WorkflowCreateRequest,
  WorkflowUpdateRequest,
} from "~/types/api";
import type {
  ExternalWorkflowInfo,
  ExternalWorkflowConfig,
} from "~/types/external-workflows";
import { externalWorkflowService } from "~/services/externalWorkflowService";
import ExternalWorkflowChat from "~/components/external/ExternalWorkflowChat";
import ExternalWorkflowViewer from "~/components/external/ExternalWorkflowViewer";
import { timeAgo } from "~/lib/dateFormatter";
import { Formik, Form, Field, ErrorMessage } from "formik";
import { Link } from "react-router";
import { useSnackbar } from "notistack";
import AuthGuard from "~/components/AuthGuard";
import Loading from "~/components/Loading";
import PinnedItemsSection from "~/components/common/PinnedItemsSection";
import PinButton from "~/components/common/PinButton";
import WorkflowEditModal from "~/components/modals/WorkflowEditModal";
import WorkflowExportModal from "~/components/modals/WorkflowExportModal";

const ErrorMessageBlock = ({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) => (
  <div className="flex items-center justify-center py-8">
    <div className="text-center">
      <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
      <h3 className="text-lg font-medium text-gray-900 mb-2">
        Error loading workflows
      </h3>
      <p className="text-gray-600 mb-4">{error}</p>
      <button
        onClick={onRetry}
        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-purple-600 hover:bg-purple-700"
      >
        <RefreshCw className="h-4 w-4 mr-2" />
        Try again
      </button>
    </div>
  </div>
);

const EmptyState = () => (
  <div className="text-center py-12">
    <div className="mx-auto h-12 w-12 text-gray-400">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1}
          d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
        />
      </svg>
    </div>
    <h3 className="mt-2 text-sm font-medium text-gray-900">No workflows</h3>
    <p className="mt-1 text-sm text-gray-500">
      Get started by creating a new workflow.
    </p>
    <div className="mt-6">
      <Link
        to="/canvas"
        className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-purple-600 hover:bg-purple-700"
      >
        <Plus className="h-4 w-4 mr-2" />
        Create Workflow
      </Link>
    </div>
  </div>
);

function WorkflowsLayout() {
  const { enqueueSnackbar } = useSnackbar();
  interface WorkflowFormValues {
    name: string;
    description: string;
    is_public: boolean;
  }

  const {
    workflows,
    isLoading,
    error,
    fetchWorkflows,
    deleteWorkflow,
    clearError,
    updateWorkflow,
    updateWorkflowStatus,
  } = useWorkflows();

  // Tab state
  const [activeTab, setActiveTab] = useState<
    "my-workflows" | "external-workflows"
  >("my-workflows");

  // My workflows state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "all" | "active" | "inactive"
  >("all");
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [editWorkflow, setEditWorkflow] = useState<Workflow | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [workflowToDelete, setWorkflowToDelete] = useState<Workflow | null>(
    null
  );
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [itemsPerPage, setItemsPerPage] = useState(6);

  // External workflows state
  const [externalWorkflows, setExternalWorkflows] = useState<
    ExternalWorkflowInfo[]
  >([]);
  const [externalLoading, setExternalLoading] = useState(false);
  const [externalError, setExternalError] = useState<string | null>(null);
  const [showAddExternalModal, setShowAddExternalModal] = useState(false);
  const [selectedExternalWorkflow, setSelectedExternalWorkflow] =
    useState<ExternalWorkflowInfo | null>(null);
  const [showExternalChatModal, setShowExternalChatModal] = useState(false);
  const [showExternalViewerModal, setShowExternalViewerModal] = useState(false);
  const [externalWorkflowToRemove, setExternalWorkflowToRemove] =
    useState<ExternalWorkflowInfo | null>(null);
  const [showRemoveExternalConfirm, setShowRemoveExternalConfirm] =
    useState(false);
  const [page, setPage] = useState(1);
  const [showExportModal, setShowExportModal] = useState(false);

  // Sayfalama hesaplamaları
  const totalItems = workflows.length; // Use workflows from the store for total count
  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
  const startIdx = (page - 1) * itemsPerPage;
  const endIdx = Math.min(startIdx + itemsPerPage, totalItems);
  const pagedWorkflows = workflows.slice(startIdx, itemsPerPage); // Use workflows from the store for paged data

  useEffect(() => {
    // Sayfa değişince, eğer mevcut sayfa yeni toplam sayfa sayısından büyükse, son sayfaya çek
    if (page > totalPages) setPage(totalPages);
  }, [totalPages, page]);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  useEffect(() => {
    if (activeTab === "external-workflows") {
      fetchExternalWorkflows();
    }
  }, [activeTab]);

  const filteredWorkflows = workflows.filter((workflow) => {
    const matchesSearch =
      workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.description?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && workflow.is_active) ||
      (statusFilter === "inactive" && !workflow.is_active);

    return matchesSearch && matchesStatus;
  });

  const handleDelete = async (workflow: Workflow) => {
    setWorkflowToDelete(workflow);
    setShowDeleteConfirm(true);
  };

  const handleFinalDeleteConfirm = async () => {
    if (!workflowToDelete) return;

    setIsDeleting(workflowToDelete.id);
    try {
      await deleteWorkflow(workflowToDelete.id);
      enqueueSnackbar("Workflow deleted successfully", { variant: "success" });
    } catch (error: any) {
      console.error("Delete workflow error:", error);

      // API'den gelen error mesajını al
      const errorMessage =
        error?.message || error?.detail || "Failed to delete workflow";

      enqueueSnackbar(errorMessage, { variant: "error" });
    } finally {
      setIsDeleting(null);
      setWorkflowToDelete(null);
      setShowDeleteConfirm(false);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteConfirm(false);
    setWorkflowToDelete(null);
  };

  const handleRetry = () => {
    clearError();
    fetchWorkflows();
  };

  const handleToggleWorkflowStatus = async (
    workflowId: string,
    isActive: boolean
  ) => {
    try {
      await updateWorkflowStatus(workflowId, isActive);

      enqueueSnackbar(
        `Workflow ${isActive ? "activated" : "deactivated"} successfully!`,
        {
          variant: "success",
          autoHideDuration: 2000,
        }
      );
    } catch (error) {
      enqueueSnackbar("Failed to update workflow status", {
        variant: "error",
        autoHideDuration: 2000,
      });
    }
  };

  // External workflow functions
  const fetchExternalWorkflows = async () => {
    setExternalLoading(true);
    setExternalError(null);
    try {
      const data = await externalWorkflowService.listExternalWorkflows();
      setExternalWorkflows(data);
    } catch (error) {
      setExternalError(
        error instanceof Error
          ? error.message
          : "Failed to fetch external workflows"
      );
    } finally {
      setExternalLoading(false);
    }
  };

  const handleRegisterExternalWorkflow = async (
    config: ExternalWorkflowConfig
  ) => {
    try {
      await externalWorkflowService.registerExternalWorkflow(config);
      enqueueSnackbar("External workflow registered successfully!", {
        variant: "success",
      });
      setShowAddExternalModal(false);
      fetchExternalWorkflows();
    } catch (error) {
      enqueueSnackbar(
        error instanceof Error
          ? error.message
          : "Failed to register external workflow",
        { variant: "error" }
      );
    }
  };

  const handleChatWithExternalWorkflow = (workflow: ExternalWorkflowInfo) => {
    setSelectedExternalWorkflow(workflow);
    setShowExternalChatModal(true);
  };

  const handleViewExternalWorkflow = (workflow: ExternalWorkflowInfo) => {
    setSelectedExternalWorkflow(workflow);
    setShowExternalViewerModal(true);
  };

  const handleRemoveExternalWorkflow = (workflow: ExternalWorkflowInfo) => {
    setExternalWorkflowToRemove(workflow);
    setShowRemoveExternalConfirm(true);
  };

  const handleFinalRemoveExternalConfirm = async () => {
    if (!externalWorkflowToRemove) return;

    try {
      await externalWorkflowService.unregisterExternalWorkflow(
        externalWorkflowToRemove.workflow_id
      );
      enqueueSnackbar("External workflow removed successfully", {
        variant: "success",
      });

      // Remove from local state
      setExternalWorkflows((prev) =>
        prev.filter(
          (w) => w.workflow_id !== externalWorkflowToRemove.workflow_id
        )
      );
    } catch (error: any) {
      console.error("Remove external workflow error:", error);
      const errorMessage =
        error?.message || error?.detail || "Failed to remove external workflow";
      enqueueSnackbar(errorMessage, { variant: "error" });
    } finally {
      setExternalWorkflowToRemove(null);
      setShowRemoveExternalConfirm(false);
    }
  };

  const handleCancelRemoveExternal = () => {
    setShowRemoveExternalConfirm(false);
    setExternalWorkflowToRemove(null);
  };

  const validateWorkflow = (values: WorkflowFormValues) => {
    const errors: Partial<WorkflowFormValues> = {};
    if (!values.name) errors.name = "Workflow name is required";
    else if (values.name.length < 3)
      errors.name = "Workflow name must be at least 3 characters";
    if (!values.description)
      errors.description = "Workflow description is required";
    else if (values.description.length < 3)
      errors.description = "Workflow description seems too short";

    return errors;
  };

  // Edit modal handlers
  const handleEditClick = (workflow: Workflow) => {
    setEditWorkflow(workflow);
    setIsEditModalOpen(true);
  };

  const handleEditModalClose = () => {
    setIsEditModalOpen(false);
    setEditWorkflow(null);
  };

  const handleWorkflowEditSubmit = async (values: WorkflowFormValues) => {
    if (!editWorkflow) return;

    const payload: WorkflowUpdateRequest = {
      name: values.name,
      description: values.description,
      is_public: values.is_public,
      flow_data: editWorkflow.flow_data, // flow_data'yı koru
    };

    try {
      await updateWorkflow(editWorkflow.id, payload);
      enqueueSnackbar("Workflow updated successfully", { variant: "success" });
      handleEditModalClose();
    } catch (e) {
      enqueueSnackbar("Failed to update workflow", { variant: "error" });
      throw e; // Re-throw to handle in modal
    }
  };

  return (
    <div className="flex h-screen bg-background text-foreground">
      <DashboardSidebar />

      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {/* Header Section */}
            <div className="mb-8">
              <div className="flex flex-col gap-6">
                {/* Title and Description */}
                <div className="flex flex-col gap-2">
                  <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                    Workflows
                  </h1>
                  <p className="text-gray-600 text-lg">
                    Create, edit, and manage your automated workflows visually
                    and intuitively.
                  </p>
                </div>

                {/* Tab Navigation */}
                <div className="flex items-center gap-2 bg-gray-100 rounded-lg p-1 w-fit">
                  <button
                    onClick={() => setActiveTab("my-workflows")}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-all duration-200 flex items-center gap-2 ${activeTab === "my-workflows"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-600 hover:text-gray-900"
                      }`}
                  >
                    <Activity className="w-4 h-4" />
                    My Workflows
                  </button>
                  <button
                    onClick={() => setActiveTab("external-workflows")}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-all duration-200 flex items-center gap-2 ${activeTab === "external-workflows"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-600 hover:text-gray-900"
                      }`}
                  >
                    <Globe className="w-4 h-4" />
                    External Workflows
                  </button>
                </div>

                {/* Status Filter Row - Only show for my workflows */}
                {activeTab === "my-workflows" && (
                  <div className="flex items-center gap-2 bg-gray-100 rounded-lg p-1 w-fit">
                    <button
                      onClick={() => setStatusFilter("all")}
                      className={`px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${statusFilter === "all"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                        }`}
                    >
                      All
                    </button>
                    <button
                      onClick={() => setStatusFilter("active")}
                      className={`px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${statusFilter === "active"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                        }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        Active
                      </div>
                    </button>
                    <button
                      onClick={() => setStatusFilter("inactive")}
                      className={`px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${statusFilter === "inactive"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                        }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                        Inactive
                      </div>
                    </button>
                  </div>
                )}

                {/* Search and Create Row - Only for my workflows */}
                {activeTab === "my-workflows" && (
                  <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                    {/* Search Bar */}
                    <div className="relative flex-1 sm:flex-none">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                      <input
                        type="search"
                        className="pl-10 pr-4 py-2 w-full sm:w-64 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 bg-white text-gray-900 placeholder-gray-500"
                        placeholder="Search workflows..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                      />
                    </div>

                    {/* Create Workflow Button */}
                    <Link
                      to="/canvas"
                      className="flex items-center justify-center gap-2 px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl hover:from-purple-700 hover:to-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl whitespace-nowrap w-full sm:w-auto"
                    >
                      <Plus className="w-5 h-5" />
                      Create Workflow
                    </Link>

                    {/* Export Workflows Button */}
                    <button
                      onClick={() => setShowExportModal(true)}
                      disabled={workflows.length === 0}
                      className="flex items-center justify-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 hover:border-gray-400 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                    >
                      <Download className="w-4 h-4" />
                      Export
                    </button>
                  </div>
                )}

                {/* Add External Workflow Row - Only for external workflows */}
                {activeTab === "external-workflows" && (
                  <div className="flex justify-end">
                    <button
                      onClick={() => setShowAddExternalModal(true)}
                      className="flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-green-600 to-teal-600 text-white rounded-xl hover:from-green-700 hover:to-teal-700 transition-all duration-200 shadow-lg hover:shadow-xl whitespace-nowrap"
                    >
                      <Plus className="w-5 h-5" />
                      Add External Workflow
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Content based on active tab */}
            {activeTab === "my-workflows" ? (
              <>
                {/* Pinned Workflows Section */}
                <PinnedItemsSection type="workflow" />

                {/* My Workflows Grid */}
                {error ? (
                  <ErrorMessageBlock error={error} onRetry={handleRetry} />
                ) : isLoading && workflows.length === 0 ? (
                  <div className="flex items-center justify-center py-12">
                    <Loading size="sm" />
                  </div>
                ) : filteredWorkflows.length === 0 ? (
                  <EmptyState />
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredWorkflows
                      .slice(startIdx, endIdx)
                      .map((workflow) => (
                        <div
                          key={workflow.id}
                          className="bg-white border border-gray-200 rounded-2xl p-6 hover:shadow-lg transition-all duration-300 hover:border-purple-200 group relative overflow-hidden"
                        >
                          {/* Status Indicator Bar */}
                          <div
                            className={`absolute top-0 left-0 right-0 h-1 ${workflow.is_active
                              ? "bg-gradient-to-r from-green-500 to-emerald-500"
                              : "bg-gradient-to-r from-gray-400 to-gray-500"
                              }`}
                          />

                          {/* Header */}
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <div
                                  className={`w-2 h-2 rounded-full ${workflow.is_active
                                    ? "bg-green-500 animate-pulse"
                                    : "bg-gray-400"
                                    }`}
                                />
                                <Link
                                  to={`/canvas?workflow=${workflow.id}`}
                                  className="text-lg font-semibold text-gray-900 hover:text-purple-600 transition-colors group-hover:text-purple-600"
                                >
                                  {workflow.name}
                                </Link>
                              </div>
                              <p className="text-sm text-gray-600 line-clamp-2">
                                {workflow.description || "No description"}
                              </p>
                            </div>

                            {/* Pin Button */}
                            <div className="flex items-center gap-2">
                              <PinButton
                                id={workflow.id}
                                type="workflow"
                                title={workflow.name}
                                description={workflow.description}
                                metadata={{
                                  status: workflow.is_public
                                    ? "Public"
                                    : "Private",
                                  lastActivity: workflow.updated_at,
                                }}
                                size="sm"
                                variant="minimal"
                              />
                            </div>
                          </div>

                          {/* Status and Visibility Badges */}
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                              <span
                                className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold rounded-full ${workflow.is_public
                                  ? "bg-blue-100 text-blue-800 border border-blue-200"
                                  : "bg-gray-100 text-gray-800 border border-gray-200"
                                  }`}
                              >
                                {workflow.is_public ? "Public" : "Private"}
                              </span>
                              <span
                                className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold rounded-full ${workflow.is_active
                                  ? "bg-green-100 text-green-800 border border-green-200"
                                  : "bg-gray-100 text-gray-600 border border-gray-200"
                                  }`}
                              >
                                {workflow.is_active ? (
                                  <>
                                    <Activity className="w-3 h-3" />
                                    Active
                                  </>
                                ) : (
                                  <>
                                    <Pause className="w-3 h-3" />
                                    Inactive
                                  </>
                                )}
                              </span>
                            </div>

                            {/* Active/Inactive Toggle */}
                            <CompactToggleSwitch
                              isActive={workflow.is_active || false}
                              onToggle={(isActive) =>
                                handleToggleWorkflowStatus(
                                  workflow.id,
                                  isActive
                                )
                              }
                            />
                          </div>

                          {/* Metadata */}
                          <div className="grid grid-cols-2 gap-4 mb-4 p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-2 text-xs text-gray-600">
                              <Calendar className="w-3 h-3" />
                              <span className="font-medium">Created:</span>
                              <span>{timeAgo(workflow.created_at)}</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-gray-600">
                              <Clock className="w-3 h-3" />
                              <span className="font-medium">Updated:</span>
                              <span>{timeAgo(workflow.updated_at)}</span>
                            </div>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                            <Link
                              to={`/canvas?workflow=${workflow.id}`}
                              className="flex items-center gap-2 text-sm text-purple-600 hover:text-purple-700 font-medium hover:bg-purple-50 px-3 py-2 rounded-lg transition-all duration-200"
                            >
                              <Play className="w-4 h-4" />
                              Open Workflow
                            </Link>

                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => handleEditClick(workflow)}
                                className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all duration-200"
                                title="Edit workflow"
                              >
                                <Pencil className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleDelete(workflow)}
                                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200"
                                title="Delete workflow"
                              >
                                <Trash className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                )}

                {/* Pagination */}
                {!error && !isLoading && filteredWorkflows.length > 0 && (
                  <div className="mt-8">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-white rounded-2xl">
                      <div></div>
                      <div className="flex items-center gap-2 justify-center">
                        <button
                          className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                          onClick={() => setPage(page - 1)}
                          disabled={page === 1}
                        >
                          <ChevronLeft className="w-5 h-5" />
                        </button>

                        {Array.from(
                          { length: totalPages },
                          (_, i) => i + 1
                        ).map((p) => (
                          <button
                            key={p}
                            onClick={() => setPage(p)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all duration-200 ${p === page
                              ? "bg-gradient-to-r from-purple-600 to-blue-600 text-white border-transparent shadow-lg"
                              : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400"
                              }`}
                          >
                            {p}
                          </button>
                        ))}

                        <button
                          className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                          onClick={() => setPage(page + 1)}
                          disabled={page === totalPages}
                        >
                          <ChevronRight className="w-5 h-5" />
                        </button>
                      </div>

                      <div className="text-sm text-gray-600 text-right">
                        Items {totalItems === 0 ? 0 : startIdx + 1} to {endIdx}{" "}
                        of {totalItems}
                      </div>
                    </div>

                    {/* Search Results Info */}
                    {searchQuery && (
                      <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-600">
                        Showing {filteredWorkflows.length} of {workflows.length}{" "}
                        workflows
                        {filteredWorkflows.length === 0 && (
                          <span className="ml-2 text-gray-500">
                            - No workflows match "{searchQuery}"
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              /* External Workflows Content */
              <div className="space-y-6">
                {externalError ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="text-center">
                      <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-gray-900 mb-2">
                        Error loading external workflows
                      </h3>
                      <p className="text-gray-600 mb-4">{externalError}</p>
                      <button
                        onClick={fetchExternalWorkflows}
                        className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                      >
                        <RefreshCw className="h-4 w-4" />
                        Retry
                      </button>
                    </div>
                  </div>
                ) : externalLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loading size="sm" />
                  </div>
                ) : externalWorkflows.length === 0 ? (
                  <div className="text-center py-12">
                    <Globe className="h-16 w-16 text-gray-300 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">
                      No External Workflows
                    </h3>
                    <p className="text-gray-600 mb-6 max-w-md mx-auto">
                      You haven't registered any external workflows yet. Add an
                      external Docker workflow to get started.
                    </p>
                    <button
                      onClick={() => setShowAddExternalModal(true)}
                      className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-600 to-teal-600 text-white rounded-xl hover:from-green-700 hover:to-teal-700 transition-all duration-200 shadow-lg hover:shadow-xl"
                    >
                      <Plus className="h-5 w-5" />
                      Add External Workflow
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {externalWorkflows.map((workflow) => (
                      <div
                        key={workflow.workflow_id}
                        className="bg-white border border-gray-200 rounded-2xl p-6 hover:shadow-lg transition-all duration-300 hover:border-green-200 group relative overflow-hidden"
                      >
                        {/* Status Indicator Bar */}
                        <div
                          className={`absolute top-0 left-0 right-0 h-1 ${workflow.connection_status === "online"
                            ? "bg-gradient-to-r from-green-500 to-emerald-500"
                            : workflow.connection_status === "offline"
                              ? "bg-gradient-to-r from-red-500 to-red-600"
                              : "bg-gradient-to-r from-yellow-500 to-orange-500"
                            }`}
                        />

                        {/* Header */}
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <div
                                className={`w-2 h-2 rounded-full ${workflow.connection_status === "online"
                                  ? "bg-green-500 animate-pulse"
                                  : workflow.connection_status === "offline"
                                    ? "bg-red-500"
                                    : "bg-yellow-500"
                                  }`}
                              />
                              <h3 className="text-lg font-semibold text-gray-900 group-hover:text-green-600 transition-colors">
                                {workflow.name}
                              </h3>
                            </div>
                            <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                              {workflow.description ||
                                "No description available"}
                            </p>
                          </div>
                        </div>

                        {/* External URL */}
                        <div className="mb-4">
                          <div className="flex items-center gap-2 text-sm text-gray-500">
                            <Globe className="w-4 h-4" />
                            <span className="font-mono text-xs bg-gray-100 px-2 py-1 rounded">
                              {workflow.external_url}
                            </span>
                          </div>
                        </div>

                        {/* Capabilities */}
                        <div className="mb-4">
                          <div className="flex flex-wrap gap-1">
                            {workflow.capabilities?.chat && (
                              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                                <MessageCircle className="w-3 h-3" />
                                Chat
                              </span>
                            )}
                            {workflow.capabilities?.memory && (
                              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-purple-100 text-purple-800 rounded-full">
                                <Clock className="w-3 h-3" />
                                Memory
                              </span>
                            )}
                            <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-gray-100 text-gray-800 rounded-full">
                              <Eye className="w-3 h-3" />
                              Read-Only
                            </span>
                          </div>
                        </div>

                        {/* Status and Actions */}
                        <div className="flex items-center justify-between">
                          <div className="text-xs text-gray-500">
                            Status:{" "}
                            <span
                              className={`font-medium ${workflow.connection_status === "online"
                                ? "text-green-600"
                                : workflow.connection_status === "offline"
                                  ? "text-red-600"
                                  : "text-yellow-600"
                                }`}
                            >
                              {workflow.connection_status}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              onClick={() =>
                                handleChatWithExternalWorkflow(workflow)
                              }
                              disabled={
                                !workflow.capabilities?.chat ||
                                workflow.connection_status !== "online"
                              }
                              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                            >
                              <MessageCircle className="w-3 h-3" />
                              Chat
                            </button>
                            <button
                              onClick={() =>
                                handleViewExternalWorkflow(workflow)
                              }
                              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                            >
                              <Eye className="w-3 h-3" />
                              View
                            </button>
                            <button
                              onClick={() =>
                                handleRemoveExternalWorkflow(workflow)
                              }
                              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                              title="Remove external workflow"
                            >
                              <X className="w-3 h-3" />
                              Remove
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Edit Modal */}
            <dialog id="modalEditWorkflow" className="modal">
              <div className="modal-box">
                <Formik
                  enableReinitialize
                  initialValues={{
                    name: editWorkflow?.name || "",
                    description: editWorkflow?.description || "",
                    is_public: editWorkflow?.is_public || false,
                  }}
                  validate={validateWorkflow}
                  onSubmit={handleWorkflowEditSubmit}
                >
                  {({ isSubmitting }) => (
                    <Form className="flex flex-col gap-4 space-y-4">
                      <div className="flex flex-col gap-2">
                        <label htmlFor="name" className="font-light">
                          Workflow Name
                        </label>
                        <Field
                          name="name"
                          type="text"
                          placeholder="Enter workflow name"
                          className="input w-full h-12 rounded-2xl border-gray-300 bg-white hover:border-gray-400"
                        />
                        <ErrorMessage
                          name="name"
                          component="p"
                          className="text-red-500 text-sm"
                        />
                      </div>

                      <div className="flex flex-col gap-2">
                        <label htmlFor="description" className="font-light">
                          Description
                        </label>
                        <Field
                          name="description"
                          type="text"
                          placeholder="Enter description"
                          className="input w-full h-12 rounded-2xl border-gray-300 bg-white hover:border-gray-400"
                        />
                        <ErrorMessage
                          name="description"
                          component="p"
                          className="text-red-500 text-sm"
                        />
                      </div>

                      <div className="flex items-center gap-2">
                        <label htmlFor="is_public" className="font-light">
                          Is Public
                        </label>
                        <Field
                          name="is_public"
                          type="checkbox"
                          className="checkbox"
                        />
                      </div>

                      <div className="modal-action">
                        <button
                          type="button"
                          className="btn"
                          onClick={() => {
                            (
                              document.getElementById(
                                "modalEditWorkflow"
                              ) as HTMLDialogElement
                            )?.close();
                            setEditWorkflow(null);
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="btn btn-primary"
                          disabled={isSubmitting}
                        >
                          {isSubmitting ? "Saving..." : "Save"}
                        </button>
                      </div>
                    </Form>
                  )}
                </Formik>
              </div>
            </dialog>
          </div>
        </div>
      </main>

      {/* Delete Confirm Modal */}
      <dialog
        open={showDeleteConfirm}
        className="modal modal-bottom sm:modal-middle"
      >
        <div className="modal-box">
          <h3 className="font-bold text-lg">Delete Workflow</h3>
          <p className="py-4">
            Are you sure you want to delete "{workflowToDelete?.name}"?
          </p>
          <div className="modal-action">
            <button className="btn btn-outline" onClick={handleCancelDelete}>
              Cancel
            </button>
            <button
              className="btn btn-error"
              onClick={handleFinalDeleteConfirm}
            >
              Delete
            </button>
          </div>
        </div>
      </dialog>

      {/* Remove External Workflow Confirm Modal */}
      <dialog
        open={showRemoveExternalConfirm}
        className="modal modal-bottom sm:modal-middle"
      >
        <div className="modal-box">
          <h3 className="font-bold text-lg">Remove External Workflow</h3>
          <p className="py-4">
            Are you sure you want to remove "{externalWorkflowToRemove?.name}"?
            This action cannot be undone.
          </p>
          <div className="modal-action">
            <button
              className="btn btn-outline"
              onClick={handleCancelRemoveExternal}
            >
              Cancel
            </button>
            <button
              className="btn btn-error"
              onClick={handleFinalRemoveExternalConfirm}
            >
              Remove
            </button>
          </div>
        </div>
      </dialog>

      {/* Add External Workflow Modal */}
      {showAddExternalModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Add External Workflow
            </h3>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const formData = new FormData(e.currentTarget);
                const config = {
                  name: formData.get("name") as string,
                  description: formData.get("description") as string,
                  host: formData.get("host") as string,
                  port: parseInt(formData.get("port") as string),
                  is_secure: formData.get("is_secure") === "on",
                  api_key: (formData.get("api_key") as string) || undefined,
                };
                await handleRegisterExternalWorkflow(config);
              }}
            >
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Name
                  </label>
                  <input
                    type="text"
                    name="name"
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    placeholder="My External Workflow"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    name="description"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    rows={3}
                    placeholder="Description of the external workflow..."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Host
                  </label>
                  <input
                    type="text"
                    name="host"
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    placeholder="localhost"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Port
                  </label>
                  <input
                    type="number"
                    name="port"
                    required
                    min="1"
                    max="65535"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    placeholder="8000"
                  />
                </div>
                <div>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      name="is_secure"
                      className="rounded"
                    />
                    <span className="text-sm text-gray-700">Use HTTPS</span>
                  </label>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    API Key (Optional)
                  </label>
                  <input
                    type="password"
                    name="api_key"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    placeholder="Enter API key if required"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowAddExternalModal(false)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  Add External Workflow
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* External Workflow Chat Modal */}
      {showExternalChatModal && selectedExternalWorkflow && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl w-full max-w-2xl mx-4 h-[600px] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-xl font-bold text-gray-900">
                Chat with {selectedExternalWorkflow.name}
              </h3>
              <button
                onClick={() => {
                  setShowExternalChatModal(false);
                  setSelectedExternalWorkflow(null);
                }}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <ExternalWorkflowChat workflow={selectedExternalWorkflow} />
            </div>
          </div>
        </div>
      )}

      {/* External Workflow Viewer Modal */}
      {selectedExternalWorkflow && (
        <ExternalWorkflowViewer
          workflow={selectedExternalWorkflow}
          isOpen={showExternalViewerModal}
          onClose={() => {
            setShowExternalViewerModal(false);
            setSelectedExternalWorkflow(null);
          }}
        />
      )}

      {/* Workflow Edit Modal */}
      <WorkflowEditModal
        isOpen={isEditModalOpen}
        workflow={editWorkflow}
        onClose={handleEditModalClose}
        onSubmit={handleWorkflowEditSubmit}
        isLoading={isLoading}
      />

      {/* Workflow Export Modal */}
      <WorkflowExportModal
        isOpen={showExportModal}
        workflows={workflows}
        onClose={() => setShowExportModal(false)}
      />
    </div>
  );
}

export default function ProtectedWorkflowsLayout() {
  return (
    <AuthGuard>
      <WorkflowsLayout />
    </AuthGuard>
  );
}
