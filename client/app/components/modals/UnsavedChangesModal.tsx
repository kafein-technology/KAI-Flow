import { forwardRef, useImperativeHandle, useRef } from "react";

interface UnsavedChangesModalProps {
  onSave: () => void;
  onDiscard: () => void;
  onCancel: () => void;
}

const UnsavedChangesModal = forwardRef<
  HTMLDialogElement,
  UnsavedChangesModalProps
>(({ onSave, onDiscard, onCancel }, ref) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useImperativeHandle(ref, () => dialogRef.current!);

  const closeAsCancel = () => {
    onCancel();
    dialogRef.current?.close();
  };

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="unsaved-changes-title"
      aria-describedby="unsaved-changes-description"
      onCancel={(event) => {
        event.preventDefault();
        closeAsCancel();
      }}
      className="fixed inset-0 m-auto h-fit w-[calc(100%_-_2rem)] max-w-lg overflow-visible bg-transparent p-0 text-left text-white backdrop:bg-black/50 backdrop:backdrop-blur-[2px]"
    >
      <div className="rounded-xl border border-gray-700 bg-gray-900 p-6 shadow-2xl shadow-black/50">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-yellow-500/20 rounded-full flex items-center justify-center">
            <svg
              className="w-5 h-5 text-yellow-500"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          </div>
          <div>
            <h3 id="unsaved-changes-title" className="font-bold text-lg text-white">
              Unsaved Changes
            </h3>
            <p className="text-sm text-gray-400">
              Your changes have not been saved
            </p>
          </div>
        </div>

        <p id="unsaved-changes-description" className="text-gray-300 mb-6">
          Do you want to save your changes before leaving this page?
        </p>

        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className="rounded-lg border border-gray-600 px-3 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
            onClick={closeAsCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-lg border border-red-600 px-3 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-900/20 hover:text-red-300"
            onClick={() => {
              onDiscard();
              dialogRef.current?.close();
            }}
          >
            Discard Changes
          </button>
          <button
            type="button"
            className="rounded-lg border border-blue-600 bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:border-blue-700 hover:bg-blue-700"
            onClick={() => {
              onSave();
              dialogRef.current?.close();
            }}
          >
            Save
          </button>
        </div>
      </div>
    </dialog>
  );
});

UnsavedChangesModal.displayName = "UnsavedChangesModal";

export default UnsavedChangesModal;
