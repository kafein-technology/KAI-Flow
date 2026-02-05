import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { Save, Clock, ToggleLeft, ToggleRight } from "~/icons/index";

interface AutoSaveSettingsModalProps {
  autoSaveEnabled: boolean;
  setAutoSaveEnabled: (enabled: boolean) => void;
  autoSaveInterval: number;
  setAutoSaveInterval: (interval: number) => void;
  lastAutoSave: Date | null;
}

const AutoSaveSettingsModal = forwardRef<
  HTMLDialogElement,
  AutoSaveSettingsModalProps
>(
  (
    {
      autoSaveEnabled,
      setAutoSaveEnabled,
      autoSaveInterval,
      setAutoSaveInterval,
      lastAutoSave,
    },
    ref
  ) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    useImperativeHandle(ref, () => dialogRef.current!);

    const [localAutoSaveEnabled, setLocalAutoSaveEnabled] =
      useState(autoSaveEnabled);
    const [localAutoSaveInterval, setLocalAutoSaveInterval] =
      useState(autoSaveInterval);

    const handleSave = () => {
      setAutoSaveEnabled(localAutoSaveEnabled);
      setAutoSaveInterval(localAutoSaveInterval);
      dialogRef.current?.close();
    };

    const handleCancel = () => {
      setLocalAutoSaveEnabled(autoSaveEnabled);
      setLocalAutoSaveInterval(autoSaveInterval);
      dialogRef.current?.close();
    };

    const formatInterval = (ms: number) => {
      const seconds = Math.floor(ms / 1000);
      if (seconds < 60) return `${seconds} saniye`;
      const minutes = Math.floor(seconds / 60);
      return `${minutes} dakika`;
    };

    return (
      <dialog
        ref={dialogRef}
        className="modal modal-bottom sm:modal-middle backdrop-blur-sm"
      >
        <div className="modal-box bg-gray-900 border border-gray-700">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-blue-500/20 rounded-full flex items-center justify-center">
              <Save className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <h3 className="font-bold text-lg text-white">
                Auto-Save Settings
              </h3>
              <p className="text-sm text-gray-400">
                Configure auto-save settings
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Auto-save toggle */}
            <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center">
                  {localAutoSaveEnabled ? (
                    <ToggleRight className="w-4 h-4 text-blue-500" />
                  ) : (
                    <ToggleLeft className="w-4 h-4 text-gray-500" />
                  )}
                </div>
                <div>
                  <h4 className="font-medium text-white">Auto-Save</h4>
                  <p className="text-xs text-gray-400">
                    Automatically save changes
                  </p>
                </div>
              </div>
              <button
                onClick={() => setLocalAutoSaveEnabled(!localAutoSaveEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${localAutoSaveEnabled ? "bg-blue-500" : "bg-gray-600"
                  }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${localAutoSaveEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                />
              </button>
            </div>

            {/* Auto-save interval */}
            <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-green-500/20 rounded-full flex items-center justify-center">
                  <Clock className="w-4 h-4 text-green-500" />
                </div>
                <div>
                  <h4 className="font-medium text-white">Save Interval</h4>
                  <p className="text-xs text-gray-400">
                    {formatInterval(localAutoSaveInterval)}
                  </p>
                </div>
              </div>
              <select
                value={localAutoSaveInterval}
                onChange={(e) =>
                  setLocalAutoSaveInterval(Number(e.target.value))
                }
                className="bg-gray-700 text-white text-sm rounded-lg px-3 py-1 border border-gray-600 focus:border-blue-500 focus:outline-none"
              >
                <option value={10000}>10 seconds</option>
                <option value={30000}>30 seconds</option>
                <option value={60000}>1 minute</option>
                <option value={300000}>5 minutes</option>
                <option value={600000}>10 minutes</option>
              </select>
            </div>

            {/* Last save info */}
            {lastAutoSave && (
              <div className="p-3 bg-gray-800/50 rounded-lg">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                  <span className="text-sm text-gray-300">
                    Last save: {lastAutoSave.toLocaleString("tr-TR")}
                  </span>
                </div>
              </div>
            )}

            {/* Info */}
            <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <p className="text-xs text-blue-300">
                💡 Auto-save feature only works for current workflows. Manual
                saving is required for new workflows.
              </p>
            </div>
          </div>

          <div className="modal-action gap-2">
            <button
              className="btn btn-outline btn-sm text-gray-400 border-gray-600 hover:bg-gray-800 hover:text-white"
              onClick={handleCancel}
            >
              Cancel
            </button>
            <button
              className="btn btn-primary btn-sm bg-blue-600 hover:bg-blue-700 text-white"
              onClick={handleSave}
            >
              Save
            </button>
          </div>
        </div>
      </dialog>
    );
  }
);

AutoSaveSettingsModal.displayName = "AutoSaveSettingsModal";

export default AutoSaveSettingsModal;
