import React, { useState } from "react";
import { X, Download, Package, Check, Square, CheckSquare } from "lucide-react";
import { exportWorkflows } from "~/services/exportService";
import type { Workflow } from "~/types/api";

interface WorkflowExportModalProps {
    isOpen: boolean;
    workflows: Workflow[];
    onClose: () => void;
}

export default function WorkflowExportModal({
    isOpen,
    workflows,
    onClose,
}: WorkflowExportModalProps) {
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [isExporting, setIsExporting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (!isOpen) return null;

    const handleToggle = (id: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    const handleSelectAll = () => {
        if (selectedIds.size === workflows.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(workflows.map((w) => w.id)));
        }
    };

    const handleExport = async () => {
        if (selectedIds.size === 0) {
            setError("Please select at least one workflow");
            return;
        }

        setIsExporting(true);
        setError(null);

        try {
            await exportWorkflows(Array.from(selectedIds));
            onClose();
        } catch (err: any) {
            setError(err?.message || "Failed to export workflows");
        } finally {
            setIsExporting(false);
        }
    };

    const allSelected = selectedIds.size === workflows.length && workflows.length > 0;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 transition-all duration-300"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
                <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[80vh] flex flex-col">
                    {/* Header */}
                    <div className="flex items-center justify-between p-6 border-b border-gray-200">
                        <div className="flex items-center gap-3">
                            <div className="flex items-center justify-center w-10 h-10 bg-purple-100 rounded-xl">
                                <Package className="w-5 h-5 text-purple-600" />
                            </div>
                            <div>
                                <h3 className="text-lg font-semibold text-gray-900">
                                    Export Workflows
                                </h3>
                                <p className="text-sm text-gray-500">
                                    Select workflows to export as ZIP
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            disabled={isExporting}
                            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto p-6">
                        {/* Select All */}
                        <button
                            onClick={handleSelectAll}
                            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-purple-600 mb-4 transition-colors"
                        >
                            {allSelected ? (
                                <CheckSquare className="w-4 h-4 text-purple-600" />
                            ) : (
                                <Square className="w-4 h-4" />
                            )}
                            {allSelected ? "Deselect All" : "Select All"}
                        </button>

                        {/* Workflow List */}
                        <div className="space-y-2">
                            {workflows.length === 0 ? (
                                <p className="text-gray-500 text-center py-8">
                                    No workflows available
                                </p>
                            ) : (
                                workflows.map((workflow) => (
                                    <button
                                        key={workflow.id}
                                        onClick={() => handleToggle(workflow.id)}
                                        className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all duration-200 text-left ${selectedIds.has(workflow.id)
                                                ? "border-purple-500 bg-purple-50"
                                                : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                                            }`}
                                    >
                                        <div
                                            className={`flex-shrink-0 w-5 h-5 rounded flex items-center justify-center ${selectedIds.has(workflow.id)
                                                    ? "bg-purple-600"
                                                    : "border-2 border-gray-300"
                                                }`}
                                        >
                                            {selectedIds.has(workflow.id) && (
                                                <Check className="w-3 h-3 text-white" />
                                            )}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="font-medium text-gray-900 truncate">
                                                {workflow.name}
                                            </p>
                                            {workflow.description && (
                                                <p className="text-sm text-gray-500 truncate">
                                                    {workflow.description}
                                                </p>
                                            )}
                                        </div>
                                        <span
                                            className={`text-xs px-2 py-1 rounded-full ${workflow.is_public
                                                    ? "bg-blue-100 text-blue-700"
                                                    : "bg-gray-100 text-gray-600"
                                                }`}
                                        >
                                            {workflow.is_public ? "Public" : "Private"}
                                        </span>
                                    </button>
                                ))
                            )}
                        </div>

                        {/* Error */}
                        {error && (
                            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                                {error}
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50 rounded-b-xl">
                        <p className="text-sm text-gray-600">
                            {selectedIds.size} of {workflows.length} selected
                        </p>
                        <div className="flex items-center gap-3">
                            <button
                                onClick={onClose}
                                disabled={isExporting}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 disabled:opacity-50 rounded-lg transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleExport}
                                disabled={isExporting || selectedIds.size === 0}
                                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                            >
                                {isExporting ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                        Exporting...
                                    </>
                                ) : (
                                    <>
                                        <Download className="w-4 h-4" />
                                        Export as ZIP
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
