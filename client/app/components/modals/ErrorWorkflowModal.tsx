import React, { useEffect, useState } from "react";
import { AlertCircle, RefreshCw, Check, ShieldAlert } from "lucide-react";
import { useWorkflows } from "~/stores/workflows";
import type { Workflow } from "~/types/api";

interface ErrorWorkflowModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentWorkflowId?: string;
  selectedErrorWorkflowId?: string;
  onSelect: (workflowId: string | null) => void;
}

const ErrorWorkflowModal = React.forwardRef<HTMLDialogElement, ErrorWorkflowModalProps>(
  ({ isOpen, onClose, currentWorkflowId, selectedErrorWorkflowId, onSelect }, ref) => {
    const { workflows, fetchWorkflows, isLoading } = useWorkflows();
    const [errorWorkflows, setErrorWorkflows] = useState<Workflow[]>([]);
    const [localSelectedId, setLocalSelectedId] = useState<string | null>(selectedErrorWorkflowId || null);

    useEffect(() => {
      if (isOpen) {
        fetchWorkflows();
        setLocalSelectedId(selectedErrorWorkflowId || null);
      }
    }, [isOpen, fetchWorkflows, selectedErrorWorkflowId]);

    useEffect(() => {
      const filtered = workflows.filter((w) => {
        if (w.id === currentWorkflowId) return false;
        const nodes = w.flow_data?.nodes || [];
        return nodes.some(
          (n) => n.type === "ErrorTrigger" || n.type === "ErrorTriggerNode"
        );
      });
      setErrorWorkflows(filtered);
    }, [workflows, currentWorkflowId]);

    const handleConfirm = () => {
      onSelect(localSelectedId);
      onClose();
    };

    return (
      <dialog
        ref={ref}
        aria-labelledby="error-handler-settings-title"
        onCancel={(event) => {
          event.preventDefault();
          onClose();
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) onClose();
        }}
        className="fixed inset-0 m-auto h-fit w-[calc(100%_-_2rem)] max-w-2xl overflow-visible bg-transparent p-0 text-left text-white backdrop:bg-black/50 backdrop:backdrop-blur-[2px]"
      >
        <div className="relative rounded-xl border border-gray-700 bg-[#18181B] p-6 shadow-2xl shadow-black/50">
          <button
            type="button"
            aria-label="Close error handler settings"
            onClick={onClose}
            className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 transition-colors hover:bg-gray-800 hover:text-white"
          >
            ✕
          </button>

          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-red-500/15 rounded-full flex items-center justify-center">
              <ShieldAlert className="w-5 h-5 text-red-400" />
            </div>
            <h3 id="error-handler-settings-title" className="font-bold text-xl text-white">
              Error Handler Settings
            </h3>
          </div>


          {isLoading ? (
            <div className="flex justify-center items-center py-8">
              <RefreshCw className="w-6 h-6 animate-spin text-blue-400" />
            </div>
          ) : errorWorkflows.length === 0 ? (
            <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-6 text-center">
              <AlertCircle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
              <h4 className="text-amber-300 font-medium mb-1">No Error Workflows Found</h4>
              <p className="text-amber-200/70 text-sm">
                Create a workflow with an <strong>Error Trigger</strong> as the entry node, then
                select it here.
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto pr-2">
              <div
                className={`p-3 rounded-lg border cursor-pointer transition-colors flex items-center justify-between ${localSelectedId === null
                    ? "border-blue-500 bg-blue-500/15"
                    : "border-gray-700 bg-gray-900/60 hover:border-blue-500/60 hover:bg-gray-800"
                  }`}
                onClick={() => setLocalSelectedId(null)}
              >
                <div>
                  <div className="font-medium text-white">None</div>
                  <div className="text-xs text-gray-400">Do not run a workflow on error</div>
                </div>
                {localSelectedId === null && <Check className="w-5 h-5 text-blue-400" />}
              </div>

              {errorWorkflows.map((wf) => (
                <div
                  key={wf.id}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors flex items-center justify-between ${localSelectedId === wf.id
                      ? "border-blue-500 bg-blue-500/15"
                      : "border-gray-700 bg-gray-900/60 hover:border-blue-500/60 hover:bg-gray-800"
                    }`}
                  onClick={() => setLocalSelectedId(wf.id)}
                >
                  <div>
                    <div className="font-medium text-white">{wf.name}</div>
                    <div className="text-xs text-gray-400 line-clamp-1">
                      {wf.description || "No description"}
                    </div>
                  </div>
                  {localSelectedId === wf.id && <Check className="w-5 h-5 text-blue-400" />}
                </div>
              ))}
            </div>
          )}

          <div className="mt-6 flex justify-end gap-2">
            <button
              type="button"
              className="rounded-lg border border-gray-600 px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg border border-blue-600 bg-blue-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:border-blue-700 hover:bg-blue-700"
              onClick={handleConfirm}
            >
              <Check className="w-4 h-4" />
              Save
            </button>
          </div>
        </div>
      </dialog>
    );
  }
);

ErrorWorkflowModal.displayName = "ErrorWorkflowModal";

export default ErrorWorkflowModal;
