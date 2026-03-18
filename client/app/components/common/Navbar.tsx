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
} from "lucide-react";
import React, { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router";
import { useSnackbar } from "notistack";
import ToggleSwitch from "./ToggleSwitch";
import WidgetExportModal from "../modals/WidgetExportModal";
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
}) => {
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isPublicTogglePending, setIsPublicTogglePending] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const deleteDialogRef = useRef<HTMLDialogElement>(null);
  const widgetExportDialogRef = useRef<HTMLDialogElement>(null);

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

  // Load handler
  const handleLoad = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const json = JSON.parse(event.target?.result as string);
        if (setCurrentWorkflow && setNodes && setEdges) {
          // Ensure we have metadata before rehydrating
          let nodeStore = useNodeStore.getState();
          if (nodeStore.nodes.length === 0) {
            await nodeStore.fetchNodes();
            await nodeStore.fetchCategories();
            nodeStore = useNodeStore.getState();
          }

          // Search both built-in and custom nodes
          const allNodesMetadata = [...(nodeStore.nodes || []), ...(nodeStore.customNodes || [])];

          const enrichedNodes = (json.flow_data?.nodes || []).map((node: any) => {
            if (!node.data?.metadata && allNodesMetadata.length > 0) {
              // Priority 1: Built-in nodes use 'name' as unique type identifier
              // Priority 2: Custom nodes use 'id'
              const metadata = allNodesMetadata.find(
                m => m.name === node.type || (m as any).id === node.type
              );

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

          setCurrentWorkflow(null);
          setNodes(enrichedNodes);
          setEdges(json.flow_data?.edges || []);
          // Update workflow name from loaded file
          if (json.name) {
            setWorkflowName(json.name);
          }
          enqueueSnackbar("Workflow loaded successfully!", {
            variant: "success",
          });
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

  // Export handler
  const handleExport = () => {
    if (!currentWorkflow) {
      enqueueSnackbar("No workflow to export!", { variant: "warning" });
      return;
    }

    // Clean up the workflow data for export
    const cleanWorkflow = {
      id: currentWorkflow.id,
      user_id: currentWorkflow.user_id,
      name: currentWorkflow.name,
      description: currentWorkflow.description,
      is_public: currentWorkflow.is_public,
      flow_data: {
        nodes: (currentWorkflow.flow_data?.nodes || []).map((node: any) => {
          // Remove React Flow internal state and redundant metadata
          const { measured, selected, dragging, width, height, ...cleanNode } = node;

          // Preserve dimensions for specifically resizable nodes like Sticky Note
          if (node.type === "StickyNoteNode") {
            if (width !== undefined) cleanNode.width = width;
            if (height !== undefined) cleanNode.height = height;
          }

          if (cleanNode.data) {
            // Remove redundant metadata that can be rehydrated from registry
            const { metadata, icon, description, displayName, inputs, outputs, ...cleanData } = cleanNode.data;
            cleanNode.data = cleanData;
          }

          return cleanNode;
        }),
        edges: (currentWorkflow.flow_data?.edges || []).map((edge: any) => {
          // Remove potential internal edge state
          const { selected, ...cleanEdge } = edge;
          return cleanEdge;
        }),
      }
    };

    const dataStr =
      "data:text/json;charset=utf-8," +
      encodeURIComponent(JSON.stringify(cleanWorkflow, null, 2));
    const downloadAnchorNode = document.createElement("a");
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute(
      "download",
      `${currentWorkflow.name || "workflow"}.json`
    );
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
    setIsDropdownOpen(false);
  };

  // Delete handler
  const handleDelete = async () => {
    if (!currentWorkflow || !deleteWorkflow) return;
    try {
      await deleteWorkflow(currentWorkflow.id);
      enqueueSnackbar("Workflow deleted successfully!", { variant: "success" });
      setCurrentWorkflow && setCurrentWorkflow(null);
      setNodes && setNodes([]);
      setEdges && setEdges([]);
      // Workflow name'ini de sıfırla
      setWorkflowName("New Workflow");
      // Workflows sayfasına yönlendir
      navigate("/workflows");
    } catch (err) {
      console.error("Delete error:", err);
      enqueueSnackbar("Workflow deleted successfully!", { variant: "error" });
    }
    deleteDialogRef.current?.close();
  };



  return (
    <>
      <header className="w-full h-16 bg-[#18181B] text-foreground  fixed top-0 left-0 z-20 ">
        <nav className="flex justify-between items-center p-4 bg-background text-foreground m-auto">
          <div className="flex items-center gap-2">
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

          <div className="flex flex-col items-center justify-center gap-3">
            <input
              type="text"
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              onBlur={handleBlur}
              placeholder="Dosya Adı"
              required
              className="text-3xl border-b-2 border-[#616161] w-full text-center focus:outline-none bg-transparent text-white"
            />
          </div>
          <div className="flex items-center space-x-4 gap-2 relative">
            {/* Workflow Public Status Toggle */}
            {currentWorkflow && updateWorkflowVisibility && (
              <div className="flex items-center gap-2">
                <ToggleSwitch
                  isActive={currentWorkflow.is_public ?? false}
                  disabled={isPublicTogglePending}
                  onToggle={async (isPublic) => {
                    if (isPublicTogglePending) return;
                    setIsPublicTogglePending(true);
                    try {
                      if (updateWorkflowVisibility) {
                        await updateWorkflowVisibility(currentWorkflow.id, isPublic);

                        // Update local state to reflect change immediately
                        if (setCurrentWorkflow) {
                          setCurrentWorkflow({
                            ...currentWorkflow,
                            is_public: isPublic,
                          });
                        }

                        enqueueSnackbar(
                          `Workflow is now ${isPublic ? "Public" : "Private"}`,
                          { variant: "success" }
                        );
                      }
                    } catch (error) {
                      enqueueSnackbar("Workflow visibility could not be updated", {
                        variant: "error",
                      });
                    } finally {
                      setIsPublicTogglePending(false);
                    }
                  }}
                  size="sm"
                  label="Activity"
                  description={
                    currentWorkflow.is_public ? "Active" : "Inactive"
                  }
                />
              </div>
            )}
            {/* Auto-save indicator */}
            {autoSaveStatus && (
              <div className="flex items-center gap-2">
                {autoSaveStatus === "saving" && (
                  <div className="flex items-center gap-1 text-green-400">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="text-xs">Saving...</span>
                  </div>
                )}
                {autoSaveStatus === "saved" && (
                  <div className="flex items-center gap-1 text-green-400">
                    <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                    <span className="text-xs">Saved</span>
                  </div>
                )}
                {autoSaveStatus === "error" && (
                  <div className="flex items-center gap-1 text-red-400">
                    <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                    <span className="text-xs">Error</span>
                  </div>
                )}
                {lastAutoSave && autoSaveStatus === "idle" && (
                  <div className="flex items-center gap-1 text-gray-400">
                    <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                    <span className="text-xs">
                      Last saved: {lastAutoSave.toLocaleTimeString()}
                    </span>
                  </div>
                )}
              </div>
            )}

            <div>
              {isLoading ? (
                <Loader className="animate-spin text-white cursor-pointer w-10 h-10 p-2 rounded-4xl" />
              ) : (
                <Save
                  className="text-white hover:text-white cursor-pointer w-10 h-10 p-2 rounded-4xl hover:bg-muted transition duration-500"
                  onClick={onSave}
                />
              )}
            </div>

            {/* Auto-save settings button */}
            {onAutoSaveSettings && (
              <div>
                <Clock
                  className="text-white hover:text-white cursor-pointer w-10 h-10 p-2 rounded-4xl hover:bg-muted transition duration-500"
                  onClick={onAutoSaveSettings}
                />
              </div>
            )}
            <div className="text-xs text-foreground relative">
              <Settings
                className="text-white hover:text-white cursor-pointer w-10 h-10 p-2 rounded-4xl hover:bg-muted transition duration-500"
                onClick={() => setIsDropdownOpen((v) => !v)}
              />
              {isDropdownOpen && (
                <div
                  ref={dropdownRef}
                  className="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-50 p-2"
                >
                  {/* Load */}
                  <button
                    className="w-full font-medium text-black text-left px-3 py-2 hover:bg-blue-50 rounded flex gap-3 justify-start items-center transition-colors duration-200"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <FileUp className="w-5 h-5 text-blue-600" />
                    Load Workflow
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/json"
                    className="hidden"
                    onChange={handleLoad}
                  />
                  {/* Export JSON */}
                  <button
                    className="w-full text-left px-3 py-2 text-black hover:bg-gray-100 rounded flex gap-3 justify-start items-center"
                    onClick={handleExport}
                  >
                    <Download className="w-5 h-5" />
                    Export JSON
                  </button>

                  {/* Export Widget */}
                  <button
                    className="w-full text-left px-3 py-2 text-black hover:bg-gray-100 rounded flex gap-3 justify-start items-center"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      setTimeout(
                        () => widgetExportDialogRef.current?.showModal(),
                        100
                      );
                    }}
                  >
                    <MessageSquare className="w-5 h-5" />
                    Export Widget
                  </button>

                  {/* Delete */}
                  <button
                    className="w-full text-left px-3 py-2 hover:bg-red-50 text-red-600 rounded flex gap-3 justify-start items-center transition-colors duration-200"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      setTimeout(
                        () => deleteDialogRef.current?.showModal(),
                        100
                      );
                    }}
                  >
                    <Trash className="w-5 h-5 text-red-600" />
                    Delete Workflow
                  </button>
                </div>
              )}
            </div>
          </div>
        </nav>
      </header>
      {/* Delete Workflow Modal */}
      <dialog ref={deleteDialogRef} className="modal">
        <div className="modal-box bg-white border border-gray-200 rounded-lg shadow-xl">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
              <Trash className="w-5 h-5 text-red-600" />
            </div>
            <h3 className="font-bold text-lg text-gray-900">Workflow'u Sil</h3>
          </div>
          <p className="py-4 text-gray-700">
            <strong className="font-semibold text-gray-900">
              {currentWorkflow?.name}
            </strong>{" "}
            workflow'unu silmek istediğine emin misin?
            <br />
            <span className="text-red-600 text-sm font-medium mt-2 block">
              ⚠️ Bu işlem geri alınamaz!
            </span>
          </p>
          <div className="modal-action">
            <form method="dialog" className="flex items-center gap-3">
              <button
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors duration-200"
                type="button"
                onClick={() => deleteDialogRef.current?.close()}
              >
                Vazgeç
              </button>
              <button
                className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors duration-200 flex items-center gap-2"
                type="button"
                onClick={handleDelete}
              >
                <Trash className="w-4 h-4" />
                Sil
              </button>
            </form>
          </div>
        </div>
      </dialog>

      <WidgetExportModal
        ref={widgetExportDialogRef}
        workflowId={currentWorkflow?.id || ""}
      />


    </>
  );
};

export default Navbar;
