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
      <dialog ref={ref} className="modal" onClose={onClose}>
        <div className="modal-box bg-white border border-gray-200 rounded-lg shadow-xl max-w-2xl">
          <form method="dialog">
            <button className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2">✕</button>
          </form>

          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
              <ShieldAlert className="w-5 h-5 text-red-600" />
            </div>
            <h3 className="font-bold text-xl text-gray-900">Error Handler Settings</h3>
          </div>


          {isLoading ? (
            <div className="flex justify-center items-center py-8">
              <RefreshCw className="w-6 h-6 animate-spin text-purple-600" />
            </div>
          ) : errorWorkflows.length === 0 ? (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
              <AlertCircle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
              <h4 className="text-amber-800 font-medium mb-1">No Error Workflows Found</h4>
              <p className="text-amber-700 text-sm">
                Create a workflow with an <strong>Error Trigger</strong> as the entry node, then
                select it here.
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto pr-2">
              <div
                className={`p-3 rounded-lg border cursor-pointer transition-colors flex items-center justify-between ${localSelectedId === null
                    ? "border-purple-500 bg-purple-50"
                    : "border-gray-200 hover:border-purple-300 hover:bg-gray-50"
                  }`}
                onClick={() => setLocalSelectedId(null)}
              >
                <div>
                  <div className="font-medium text-gray-900">None</div>
                  <div className="text-xs text-gray-500">Do not run a workflow on error</div>
                </div>
                {localSelectedId === null && <Check className="w-5 h-5 text-purple-600" />}
              </div>

              {errorWorkflows.map((wf) => (
                <div
                  key={wf.id}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors flex items-center justify-between ${localSelectedId === wf.id
                      ? "border-purple-500 bg-purple-50"
                      : "border-gray-200 hover:border-purple-300 hover:bg-gray-50"
                    }`}
                  onClick={() => setLocalSelectedId(wf.id)}
                >
                  <div>
                    <div className="font-medium text-gray-900">{wf.name}</div>
                    <div className="text-xs text-gray-500 line-clamp-1">
                      {wf.description || "No description"}
                    </div>
                  </div>
                  {localSelectedId === wf.id && <Check className="w-5 h-5 text-purple-600" />}
                </div>
              ))}
            </div>
          )}

          <div className="modal-action mt-6 gap-2">
            <button
              type="button"
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors duration-200 text-gray-700"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="button"
              className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-all duration-200 shadow-md flex items-center gap-2"
              onClick={handleConfirm}
            >
              <Check className="w-4 h-4" />
              Save
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button type="submit">close</button>
        </form>
      </dialog>
    );
  }
);

ErrorWorkflowModal.displayName = "ErrorWorkflowModal";

export default ErrorWorkflowModal;
