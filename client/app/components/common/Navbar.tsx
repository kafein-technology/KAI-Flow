import {
  ArrowLeft,
  Save,
  Settings,
  FileUp,
  Download,
  Trash,
  Loader,
  Clock,
  MessageSquare,
  ShieldAlert,
  StopCircle,
  Undo2,
  Redo2,
} from "lucide-react";
import React, { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router";
import { useSnackbar } from "notistack";
import ToggleSwitch from "./ToggleSwitch";
import WidgetExportModal from "../modals/WidgetExportModal";
import ErrorWorkflowModal from "../modals/ErrorWorkflowModal";
import WorkflowService from "~/services/workflows";
import { useNodeStore } from "~/stores/nodes";

interface NavbarProps {
  workflowName: string;
  setWorkflowName: (name: string) => void;
  onSave: () => void;
  currentWorkflow?: any;
  setCurrentWorkflow?: (wf: any) => void;
  deleteWorkflow?: (id: string) => Promise<void>;
  setNodes?: (nodes: any[]) => void;
  setEdges?: (edges: any[]) => void;
  isLoading: boolean;
  checkUnsavedChanges?: (url: string) => boolean;
  autoSaveStatus?: "idle" | "saving" | "saved" | "error";
  lastAutoSave?: Date | null;
  onAutoSaveSettings?: () => void;
  updateWorkflowStatus?: (id: string, is_active: boolean) => Promise<void>;
  updateWorkflowVisibility?: (id: string, is_public: boolean) => Promise<void>;
  onImportStart?: () => void;
  onWorkflowImported?: (nodes: any[], edges: any[]) => void;
  onUndo?: () => void;
  onRedo?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  executionLoading?: boolean;
  activeExecutionId?: string | null;
  currentExecution?: any;
  onCancelExecution?: (executionId: string) => Promise<void>;
  hasUnsavedChanges?: boolean;
}

const Navbar: React.FC<NavbarProps> = ({
  workflowName,
  setWorkflowName,
  onSave,
  currentWorkflow,
  setCurrentWorkflow,
  deleteWorkflow,
  setNodes,
  setEdges,
  isLoading,
  checkUnsavedChanges,
  autoSaveStatus,
  lastAutoSave,
  onAutoSaveSettings,
  updateWorkflowVisibility,
  onImportStart,
  onWorkflowImported,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
  executionLoading,
  activeExecutionId,
  currentExecution,
  onCancelExecution,
  hasUnsavedChanges = false,
}) => {
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isPublicTogglePending, setIsPublicTogglePending] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const deleteDialogRef = useRef<HTMLDialogElement>(null);
  const widgetExportDialogRef = useRef<HTMLDialogElement>(null);
  const errorWorkflowDialogRef = useRef<HTMLDialogElement>(null);

  const [isErrorModalOpen, setIsErrorModalOpen] = useState(false);
  const [errorWorkflowId, setErrorWorkflowId] = useState<string | undefined>(
    () =>
      currentWorkflow?.error_workflow ||
      currentWorkflow?.flow_data?.settings?.error_workflow_id ||
      undefined
  );

  useEffect(() => {
    setErrorWorkflowId(
      currentWorkflow?.error_workflow ||
      currentWorkflow?.flow_data?.settings?.error_workflow_id ||
      undefined
    );
  }, [currentWorkflow]);

  // Dışarı tıklayınca dropdown'u kapat
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false);
      }
    }
    if (isDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    } else {
      document.removeEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isDropdownOpen]);

  // Determine the base path from Vite env
  const baseUrl = (window.VITE_BASE_PATH?.endsWith('/')
    ? window.VITE_BASE_PATH.slice(0, -1)
    : window.VITE_BASE_PATH) || "";

  // Helper to prepend base url
  const getPath = (path: string) => `${baseUrl}${path}`;

  const handleBlur = () => {
    if (workflowName.trim() === "") {
      setWorkflowName("New Workflow");
    }
    enqueueSnackbar("Workflow name updated", { variant: "success" });
  };

  const handleLoad = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const json = JSON.parse(event.target?.result as string);
        if (setCurrentWorkflow && setNodes && setEdges) {
          let nodeStore = useNodeStore.getState();
          if (nodeStore.nodes.length === 0) {
            await nodeStore.fetchNodes();
            await nodeStore.fetchCategories();
          }
          if (nodeStore.customNodes.length === 0) {
            await nodeStore.fetchCustomNodes();
          }
          nodeStore = useNodeStore.getState();

          const allNodesMetadata = [...(nodeStore.nodes || []), ...(nodeStore.customNodes || [])];
          const enrichedNodes = (json.flow_data?.nodes || []).map((node: any) => {
            if (!node.data?.metadata && allNodesMetadata.length > 0) {
              const metadata = allNodesMetadata.find(
                m => m.name === node.type || (m as any).id === node.type
              ) as any;

              if (metadata) {
                return {
                  ...node,
                  data: {
                    ...node.data,
                    metadata: metadata,
                    icon: metadata.icon,
                    description: metadata.description,
                    displayName: metadata.display_name,
                    inputs: metadata.inputs,
                    outputs: metadata.outputs,
                  }
                };
              }
            }
            return node;
          });

          if (onImportStart) onImportStart();

          if (currentWorkflow && setCurrentWorkflow) {
            setCurrentWorkflow({
              ...currentWorkflow,
              name: json.name || currentWorkflow.name,
              flow_data: {
                ...currentWorkflow.flow_data,
                nodes: enrichedNodes,
                edges: json.flow_data?.edges || []
              }
            });
          } else if (setCurrentWorkflow) {
            setCurrentWorkflow(null);
          }

          setNodes(enrichedNodes);
          setEdges(json.flow_data?.edges || []);
          onWorkflowImported?.(enrichedNodes, json.flow_data?.edges || []);
          if (json.name) {
            setWorkflowName(json.name);
          }
          enqueueSnackbar("Workflow loaded successfully!", { variant: "success" });
        }
      } catch (err) {
        console.error("Load error:", err);
        enqueueSnackbar("Invalid JSON file!", { variant: "error" });
      }
    };
    reader.readAsText(file);
    setIsDropdownOpen(false);
    e.target.value = "";
  };

  const handleExport = () => {
    if (!currentWorkflow) {
      enqueueSnackbar("No workflow to export!", { variant: "warning" });
      return;
    }

    const cleanWorkflow = {
      id: currentWorkflow.id,
      user_id: currentWorkflow.user_id,
      name: currentWorkflow.name,
      description: currentWorkflow.description,
      is_public: currentWorkflow.is_public,
      flow_data: {
        nodes: (currentWorkflow.flow_data?.nodes || []).map((node: any) => {
          const { measured, selected, dragging, width, height, ...cleanNode } = node;
          if (node.type === "StickyNoteNode") {
            if (width !== undefined) cleanNode.width = width;
            if (height !== undefined) cleanNode.height = height;
          }
          if (cleanNode.data) {
            const { metadata, icon, description, displayName, inputs, outputs, ...cleanData } = cleanNode.data;
            cleanNode.data = cleanData;
          }
          return cleanNode;
        }),
        edges: (currentWorkflow.flow_data?.edges || []).map((edge: any) => {
          const { selected, ...cleanEdge } = edge;
          return cleanEdge;
        }),
      }
    };

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(cleanWorkflow, null, 2));
    const downloadAnchorNode = document.createElement("a");
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `${currentWorkflow.name || "workflow"}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
    setIsDropdownOpen(false);
  };

  const handleDelete = async () => {
    if (!currentWorkflow || !deleteWorkflow) return;
    try {
      await deleteWorkflow(currentWorkflow.id);
      enqueueSnackbar("Workflow deleted successfully!", { variant: "success" });
      setCurrentWorkflow && setCurrentWorkflow(null);
      setNodes && setNodes([]);
      setEdges && setEdges([]);
      setWorkflowName("New Workflow");
      navigate("/workflows");
    } catch (err) {
      console.error("Delete error:", err);
      enqueueSnackbar("Failed to delete workflow", { variant: "error" });
    }
    deleteDialogRef.current?.close();
  };

  // Show save status: during save action OR when at saved state (no unsaved changes)
  const showAutoSaveStatus =
    autoSaveStatus === "saving" ||
    autoSaveStatus === "error" ||
    (currentWorkflow && !hasUnsavedChanges);

  const saveStatusLabel =
    autoSaveStatus === "saving"
      ? "Saving..."
      : autoSaveStatus === "error"
        ? "Error"
        : currentWorkflow && !hasUnsavedChanges
          ? "Saved"
          : null;

  const showExecutionStatus =
    executionLoading ||
    !!activeExecutionId ||
    (currentExecution &&
      (currentExecution.status === "running" ||
        currentExecution.status === "pending"));

  return (
    <>
      <header className="w-full h-16 bg-[#18181B] text-foreground fixed top-0 left-0 z-20">
        <nav className="relative flex items-center p-4 bg-background text-foreground m-auto">
          <div className="flex items-center gap-2 z-10">
            <Link
              to="/workflows"
              className="flex items-center"
              onClick={(e) => {
                if (checkUnsavedChanges) {
                  const canNavigate = checkUnsavedChanges(getPath("/workflows"));
                  if (!canNavigate) e.preventDefault();
                }
              }}
            >
              <ArrowLeft className="text-white cursor-pointer w-10 h-10 p-2 rounded-4xl hover:bg-muted transition duration-500" />
            </Link>
          </div>

          <div className="absolute inset-x-0 flex justify-center items-center px-48 pointer-events-none z-0">
            <input
              type="text"
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              onBlur={handleBlur}
              placeholder="Dosya Adı"
              className="pointer-events-auto text-lg font-medium text-white/90 bg-transparent px-4 py-1.5 rounded-md border border-transparent hover:border-white/20 focus:border-white/30 hover:bg-white/5 focus:bg-white/10 focus:outline-none transition-all duration-300 text-center w-full max-w-[400px] focus:max-w-[800px]"
            />
          </div>

          <div className="flex items-center gap-2 relative ml-auto z-10">
            <div className={`flex items-center justify-end shrink-0 ${showExecutionStatus ? "min-w-[9.5rem]" : ""}`}>
              {showExecutionStatus && (
                <div className="flex items-center gap-2 text-gray-400 whitespace-nowrap">
                  <Loader className="w-3.5 h-3.5 animate-spin shrink-0" />
                  <span className="text-xs font-medium">Executing...</span>
                  {onCancelExecution && (
                    <button
                      onClick={async () => {
                        const runId = activeExecutionId || (currentExecution && (currentExecution.status === "running" || currentExecution.status === "pending") ? currentExecution.id : null);
                        if (runId && confirm("Are you sure you want to cancel this execution?")) {
                          try {
                            await onCancelExecution(runId);
                            enqueueSnackbar("Workflow execution cancel requested.", { variant: "info" });
                          } catch (err) {
                            console.error("Failed to cancel execution:", err);
                            enqueueSnackbar("Failed to cancel execution.", { variant: "error" });
                          }
                        }
                      }}
                      className={`px-2 py-0.5 text-[11px] text-red-500 hover:text-red-400 border border-red-500/30 hover:border-red-500/50 rounded transition-colors cursor-pointer shrink-0 ${activeExecutionId || (currentExecution && (currentExecution.status === "running" || currentExecution.status === "pending"))
                          ? "visible"
                          : "invisible pointer-events-none"
                        }`}
                      title="Cancel Execution"
                      aria-hidden={!(activeExecutionId || (currentExecution && (currentExecution.status === "running" || currentExecution.status === "pending")))}
                      tabIndex={activeExecutionId || (currentExecution && (currentExecution.status === "running" || currentExecution.status === "pending")) ? 0 : -1}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              )}
            </div>

            <div
              className={`grid transition-[grid-template-columns] duration-300 ease-in-out ${showAutoSaveStatus ? "grid-cols-[1fr]" : "grid-cols-[0fr]"
                }`}
              aria-live="polite"
            >
              <div className="overflow-hidden min-w-0">
                <div
                  className={`flex items-center gap-1 text-xs whitespace-nowrap tabular-nums transition-opacity duration-300 ${
                    showAutoSaveStatus ? "opacity-100" : "opacity-0"
                  } ${autoSaveStatus === "error"
                      ? "text-red-400"
                      : autoSaveStatus === "saving"
                        ? "text-yellow-400"
                        : "text-green-400"
                    }`}
                >
                  <div
                    className={`w-2 h-2 rounded-full shrink-0 ${autoSaveStatus === "error"
                        ? "bg-red-400"
                        : autoSaveStatus === "saving"
                          ? "bg-yellow-400 animate-pulse"
                          : "bg-green-400"
                      }`}
                  />
                  <span>{saveStatusLabel || "Saved"}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center shrink-0">
              <button
                type="button"
                className={`p-0 border-0 bg-transparent rounded-4xl transition duration-500 ${canUndo ? "cursor-pointer hover:bg-muted" : "cursor-not-allowed"
                  }`}
                onClick={canUndo ? onUndo : undefined}
                disabled={!canUndo}
                aria-label="Undo (Ctrl+Z)"
                title="Undo (Ctrl+Z)"
              >
                <Undo2
                  className={`w-10 h-10 p-2 ${canUndo ? "text-white" : "text-white/30"
                    }`}
                />
              </button>
              <button
                type="button"
                className={`p-0 border-0 bg-transparent rounded-4xl transition duration-500 ${canRedo ? "cursor-pointer hover:bg-muted" : "cursor-not-allowed"
                  }`}
                onClick={canRedo ? onRedo : undefined}
                disabled={!canRedo}
                aria-label="Redo (Ctrl+Y)"
                title="Redo (Ctrl+Y)"
              >
                <Redo2
                  className={`w-10 h-10 p-2 ${canRedo ? "text-white" : "text-white/30"
                    }`}
                />
              </button>
            </div>

            {currentWorkflow && updateWorkflowVisibility && (
              <ToggleSwitch
                theme="dark"
                isActive={currentWorkflow.is_public ?? false}
                disabled={isPublicTogglePending}
                onToggle={async (isPublic) => {
                  if (isPublicTogglePending) return;
                  setIsPublicTogglePending(true);
                  try {
                    await updateWorkflowVisibility(currentWorkflow.id, isPublic);
                    if (setCurrentWorkflow) {
                      setCurrentWorkflow({ ...currentWorkflow, is_public: isPublic });
                    }
                    enqueueSnackbar(`Workflow is now ${isPublic ? "Public" : "Private"}`, { variant: "success" });
                  } catch (error) {
                    enqueueSnackbar("Workflow visibility could not be updated", { variant: "error" });
                  } finally {
                    setIsPublicTogglePending(false);
                  }
                }}
                size="sm"
                label="Activity"
                description={currentWorkflow.is_public ? "Active" : "Inactive"}
              />
            )}

            {isLoading ? (
              <Loader className="animate-spin text-white w-10 h-10 p-2 rounded-4xl shrink-0" />
            ) : (
              <Save
                className="text-white cursor-pointer w-10 h-10 p-2 rounded-4xl hover:bg-muted transition duration-500 shrink-0"
                onClick={onSave}
              />
            )}

            <div className="relative shrink-0" ref={dropdownRef}>
              <Settings
                className="text-white cursor-pointer w-10 h-10 p-2 rounded-4xl hover:bg-muted transition duration-500"
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              />
              {isDropdownOpen && (
                <div
                  className="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-50 p-2"
                >
                  <button
                    className="w-full text-left px-3 py-2 text-black hover:bg-gray-100 rounded flex gap-3 items-center"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <FileUp className="w-5 h-5" />
                    Load Workflow
                  </button>
                  <input ref={fileInputRef} type="file" accept="application/json" className="hidden" onChange={handleLoad} />

                  <button className="w-full text-left px-3 py-2 text-black hover:bg-gray-100 rounded flex gap-3 items-center" onClick={handleExport}>
                    <Download className="w-5 h-5" />
                    Export JSON
                  </button>

                  {onAutoSaveSettings && (
                    <button
                      className="w-full text-left px-3 py-2 text-black hover:bg-gray-100 rounded flex gap-3 items-center"
                      onClick={() => {
                        setIsDropdownOpen(false);
                        onAutoSaveSettings();
                      }}
                    >
                      <Clock className="w-5 h-5" />
                      Auto-Save Settings
                    </button>
                  )}

                  <button
                    className="w-full text-left px-3 py-2 text-black hover:bg-gray-100 rounded flex gap-3 items-center"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      setTimeout(() => widgetExportDialogRef.current?.showModal(), 100);
                    }}
                  >
                    <MessageSquare className="w-5 h-5" />
                    Export Widget
                  </button>

                  <button
                    className="w-full text-left px-3 py-2 text-black hover:bg-red-50 hover:text-red-600 rounded flex gap-3 items-center transition-colors"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      setIsErrorModalOpen(true);
                      setTimeout(() => errorWorkflowDialogRef.current?.showModal(), 100);
                    }}
                  >
                    <ShieldAlert className="w-5 h-5" />
                    Error Handler
                  </button>

                  <button
                    className="w-full text-left px-3 py-2 hover:bg-red-50 text-red-600 rounded flex gap-3 items-center transition-colors"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      setTimeout(() => deleteDialogRef.current?.showModal(), 100);
                    }}
                  >
                    <Trash className="w-5 h-5" />
                    Delete Workflow
                  </button>
                </div>
              )}
            </div>
          </div>
        </nav>
      </header>

      <dialog ref={deleteDialogRef} className="modal">
        <div className="modal-box bg-white border border-gray-200 rounded-lg shadow-xl">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
              <Trash className="w-5 h-5 text-red-600" />
            </div>
            <h3 className="font-bold text-lg text-gray-900">Delete Workflow</h3>
          </div>
          <p className="py-4 text-gray-700">
            Are you sure you want to delete the workflow <strong className="font-semibold text-gray-900">{currentWorkflow?.name}</strong>?
            <br />
            <span className="text-red-600 text-sm font-medium mt-2 block">⚠️ This action cannot be undone!</span>
          </p>
          <div className="modal-action">
            <form method="dialog" className="flex items-center gap-3">
              <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50" type="button" onClick={() => deleteDialogRef.current?.close()}>Cancel</button>
              <button className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg flex items-center gap-2" type="button" onClick={handleDelete}>
                <Trash className="w-4 h-4" />
                Delete
              </button>
            </form>
          </div>
        </div>
      </dialog>

      <WidgetExportModal ref={widgetExportDialogRef} workflowId={currentWorkflow?.id || ""} />

      <ErrorWorkflowModal
        ref={errorWorkflowDialogRef}
        isOpen={isErrorModalOpen}
        onClose={() => {
          setIsErrorModalOpen(false);
          errorWorkflowDialogRef.current?.close();
        }}
        currentWorkflowId={currentWorkflow?.id}
        selectedErrorWorkflowId={errorWorkflowId}
        onSelect={async (id) => {
          setErrorWorkflowId(id || undefined);
          if (!currentWorkflow || !setCurrentWorkflow) return;

          const updatedWorkflow = {
            ...currentWorkflow,
            error_workflow: id,
            flow_data: {
              ...currentWorkflow.flow_data,
              settings: { ...currentWorkflow.flow_data?.settings, error_workflow_id: id }
            }
          };
          setCurrentWorkflow(updatedWorkflow);

          try {
            const saved = await WorkflowService.updateWorkflow(currentWorkflow.id, {
              error_workflow: id,
              flow_data: updatedWorkflow.flow_data,
            });
            setCurrentWorkflow(saved);
            setErrorWorkflowId(saved.error_workflow || undefined);
            enqueueSnackbar(id ? "Error handler workflow updated" : "Error handler removed", { variant: "success" });
          } catch (error: any) {
            setErrorWorkflowId(currentWorkflow.error_workflow || undefined);
            setCurrentWorkflow(currentWorkflow);
            enqueueSnackbar(error?.response?.data?.detail || error?.message || "Failed to update error handler", { variant: "error" });
          }
        }}
      />
    </>
  );
};

export default Navbar;