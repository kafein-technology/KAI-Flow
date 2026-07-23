import React, { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";

interface DeleteConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
  isLoading?: boolean;
}

export default function DeleteConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  title = "Delete Execution",
  message = "Are you sure you want to delete this execution? This action cannot be undone.",
  confirmText = "Delete",
  cancelText = "Cancel",
  isLoading = false
}: DeleteConfirmationModalProps) {
  const [shouldRender, setShouldRender] = useState(isOpen);
  const [isClosing, setIsClosing] = useState(false);
  const [visibleContent, setVisibleContent] = useState({ title, message });

  useEffect(() => {
    if (isOpen) {
      setVisibleContent({ title, message });
      setShouldRender(true);
      setIsClosing(false);
      return;
    }

    if (!shouldRender) return;

    setIsClosing(true);
    const timer = window.setTimeout(() => {
      setShouldRender(false);
      setIsClosing(false);
    }, 200);

    return () => window.clearTimeout(timer);
  }, [isOpen, message, shouldRender, title]);

  if (!shouldRender) return null;

  const handleConfirm = () => {
    onConfirm();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-50 bg-black/40 backdrop-blur-sm ${
          isClosing
            ? "animate-modal-backdrop-out"
            : "animate-modal-backdrop-in"
        }`}
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <div
          className={`bg-white rounded-lg shadow-xl max-w-md w-full ${
            isClosing
              ? "animate-modal-content-out"
              : "animate-modal-content-in"
          }`}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-8 h-8 bg-red-100 rounded-full">
                <AlertTriangle className="w-4 h-4 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">
                {visibleContent.title}
              </h3>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              disabled={isLoading}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            <p className="text-gray-600">{visibleContent.message}</p>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
            <button
              onClick={onClose}
              className="btn btn-outline"
              disabled={isLoading}
            >
              {cancelText}
            </button>
            <button
              onClick={handleConfirm}
              disabled={isLoading}
              className="btn btn-error"
            >
              {isLoading ? "Deleting..." : confirmText}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
