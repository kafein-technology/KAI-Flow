import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Clock3,
  Database,
  FileArchive,
  FolderOpen,
  Loader2,
  Trash2,
} from "lucide-react";

import CredentialSelector from "../../credentials/CredentialSelector";
import { apiClient } from "~/lib/api-client";
import { API_ENDPOINTS } from "~/lib/config";
import { useWorkflows } from "~/stores/workflows";
import type { NodeProperty } from "../types";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

interface NodeModelArtifactSourceProps {
  property: NodeProperty;
  values: any;
  setFieldValue: (name: string, value: any) => void;
  nodeId?: string;
}

type SourceMode = "local" | "minio";
type BrowserFile = File & { webkitRelativePath?: string };
type ManagedArtifactStatus = {
  artifact_id?: string;
  expires_at?: string;
  available?: boolean;
};

const MAX_DIRECTORY_FILES = 512;
const FALLBACK_MANAGED_UPLOAD_MAX_BYTES = 8 * 1024 * 1024 * 1024;

const emptyLocalSource = () => ({
  source_type: "path",
  storage: "local_path",
  path: "",
});

const emptyMinioSource = () => ({
  source_type: "minio",
  storage: "minio",
  credential_id: "",
  bucket: "",
  object_key: "",
});

const inputClass =
  "min-w-0 flex-1 rounded-l-lg border border-r-0 border-slate-600 bg-[#10182c] " +
  "px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none";

function formatBytes(value: number | undefined): string {
  if (!value || value < 1) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const amount = value / 1024 ** index;
  return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDuration(seconds: number): string {
  if (seconds % 86400 === 0) return `${seconds / 86400} day${seconds === 86400 ? "" : "s"}`;
  if (seconds % 3600 === 0) return `${seconds / 3600} hour${seconds === 3600 ? "" : "s"}`;
  return `${Math.max(1, Math.round(seconds / 60))} minutes`;
}

function localDisplayPath(value: Record<string, any>): string {
  if (value.source_type === "path") return String(value.path || "");
  if (value.artifact_id && value.name) return `managed://${value.name}`;
  return "";
}

function minioDisplayPath(value: Record<string, any>): string {
  const bucket = String(value.bucket || "").replace(/^\/+|\/+$/g, "");
  const objectKey = String(value.object_key || "").replace(/^\/+/, "");
  return bucket && objectKey ? `${bucket}/${objectKey}` : bucket || objectKey;
}

function parseMinioPath(path: string): { bucket: string; object_key: string } {
  const normalized = path.trim().replace(/^minio:\/\//i, "").replace(/^\/+/, "");
  const separator = normalized.indexOf("/");
  if (separator < 1) return { bucket: normalized, object_key: "" };
  return {
    bucket: normalized.slice(0, separator),
    object_key: normalized.slice(separator + 1),
  };
}

export function NodeModelArtifactSource({
  property,
  values,
  setFieldValue,
  nodeId,
}: NodeModelArtifactSourceProps) {
  const workflowId = useWorkflows((state) => state.currentWorkflow?.id);
  const rawValue = values[property.name];
  const value: Record<string, any> =
    rawValue && typeof rawValue === "object" && !Array.isArray(rawValue)
      ? rawValue
      : emptyLocalSource();
  const sourceMode: SourceMode = value.source_type === "minio" ? "minio" : "local";

  const fileInputRef = useRef<HTMLInputElement>(null);
  const directoryInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const localSourceRef = useRef<Record<string, any>>(
    sourceMode === "local" ? value : emptyLocalSource(),
  );
  const minioSourceRef = useRef<Record<string, any>>(
    sourceMode === "minio" ? value : emptyMinioSource(),
  );
  const [browserMenuOpen, setBrowserMenuOpen] = useState(false);
  const [modelAcceptedFiles, setModelAcceptedFiles] = useState("");
  const [scannerVersion, setScannerVersion] = useState("");
  const [managedUploadMaxBytes, setManagedUploadMaxBytes] = useState(
    FALLBACK_MANAGED_UPLOAD_MAX_BYTES,
  );
  const [artifactMaxBytes, setArtifactMaxBytes] = useState<number>();
  const [managedRetentionSeconds, setManagedRetentionSeconds] = useState(24 * 60 * 60);
  const [postScanRetentionSeconds, setPostScanRetentionSeconds] = useState(60 * 60);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState("");
  const [artifactExpired, setArtifactExpired] = useState(false);
  const [managedArtifactStatus, setManagedArtifactStatus] =
    useState<ManagedArtifactStatus | null>(null);
  const [pathDraft, setPathDraft] = useState(
    sourceMode === "minio" ? minioDisplayPath(value) : localDisplayPath(value),
  );

  useEffect(() => {
    if (sourceMode === "minio") {
      minioSourceRef.current = value;
    } else {
      localSourceRef.current = value;
    }
  }, [sourceMode, value]);

  useEffect(() => {
    let active = true;
    apiClient
      .get<{
        extensions?: string[];
        version?: string;
        limits?: {
          artifact_max_bytes?: number;
          managed_upload_max_bytes?: number;
        };
        managed_artifact_policy?: {
          unscanned_retention_seconds?: number;
          post_scan_retention_seconds?: number;
        };
      }>(
        API_ENDPOINTS.MODEL_ARTIFACTS.CAPABILITIES,
      )
      .then((capabilities) => {
        if (!active) return;
        const extensions = new Set(
          (capabilities.extensions || []).filter(
            (extension): extension is string =>
              typeof extension === "string" && extension.startsWith("."),
          ),
        );
        extensions.add(".zip");
        setModelAcceptedFiles(Array.from(extensions).sort().join(","));
        setScannerVersion(capabilities.version || "");
        const uploadLimit = capabilities.limits?.managed_upload_max_bytes;
        if (Number.isFinite(uploadLimit) && Number(uploadLimit) > 0) {
          setManagedUploadMaxBytes(Number(uploadLimit));
        }
        const artifactLimit = capabilities.limits?.artifact_max_bytes;
        if (Number.isFinite(artifactLimit) && Number(artifactLimit) > 0) {
          setArtifactMaxBytes(Number(artifactLimit));
        }
        const unscannedRetention =
          capabilities.managed_artifact_policy?.unscanned_retention_seconds;
        if (Number.isFinite(unscannedRetention) && Number(unscannedRetention) > 0) {
          setManagedRetentionSeconds(Number(unscannedRetention));
        }
        const postScanRetention =
          capabilities.managed_artifact_policy?.post_scan_retention_seconds;
        if (Number.isFinite(postScanRetention) && Number(postScanRetention) > 0) {
          setPostScanRetentionSeconds(Number(postScanRetention));
        }
      })
      .catch(() => {
        // The backend validates the artifact when capability discovery is unavailable.
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const artifactId = String(value.artifact_id || "").trim();
    if (!artifactId || value.storage !== "managed") return;
    let active = true;
    const refreshStatus = async () => {
      try {
        const status = await apiClient.get<ManagedArtifactStatus>(
          API_ENDPOINTS.MODEL_ARTIFACTS.GET(artifactId),
        );
        if (active) setManagedArtifactStatus(status);
      } catch (error: unknown) {
        const typedError = error as {
          status?: number;
          response?: { status?: number };
        };
        const statusCode = typedError.status ?? typedError.response?.status;
        if (active && statusCode === 404) {
          setManagedArtifactStatus({ artifact_id: artifactId, available: false });
        }
        // Retain the last known state for transient failures; execution remains authoritative.
      }
    };
    void refreshStatus();
    const interval = window.setInterval(() => void refreshStatus(), 60_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [value.artifact_id, value.storage]);

  const currentManagedStatus =
    managedArtifactStatus?.artifact_id === value.artifact_id
      ? managedArtifactStatus
      : null;
  const effectiveExpiresAt = currentManagedStatus?.expires_at || value.expires_at;
  const artifactUnavailable = currentManagedStatus?.available === false;

  useEffect(() => {
    const refreshExpiry = () => {
      const expiresAt = Date.parse(String(effectiveExpiresAt || ""));
      setArtifactExpired(Number.isFinite(expiresAt) && expiresAt <= Date.now());
    };
    const initialTimer = window.setTimeout(refreshExpiry, 0);
    const interval = window.setInterval(refreshExpiry, 60_000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(interval);
    };
  }, [effectiveExpiresAt]);

  useEffect(() => {
    setPathDraft(
      sourceMode === "minio" ? minioDisplayPath(value) : localDisplayPath(value),
    );
  }, [
    sourceMode,
    value.artifact_id,
    value.name,
    value.path,
    value.bucket,
    value.object_key,
  ]);

  useEffect(() => {
    const closeMenu = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setBrowserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", closeMenu);
    return () => document.removeEventListener("mousedown", closeMenu);
  }, []);

  const setSource = (next: Record<string, any>) => {
    if (next.source_type === "minio") {
      minioSourceRef.current = next;
    } else {
      localSourceRef.current = next;
    }
    setFieldValue(property.name, next);
  };

  const releaseManagedArtifact = async (artifactId: unknown) => {
    const normalizedId = String(artifactId || "").trim();
    if (!normalizedId) return;
    try {
      await apiClient.delete(API_ENDPOINTS.MODEL_ARTIFACTS.DELETE(normalizedId));
    } catch {
      // The new selection stays valid; deployment retention can clean an orphan later.
    }
  };

  const replaceSource = (next: Record<string, any>) => {
    const previousArtifactId = value.artifact_id;
    if (previousArtifactId !== next.artifact_id) setManagedArtifactStatus(null);
    setSource(next);
    if (previousArtifactId && previousArtifactId !== next.artifact_id) {
      void releaseManagedArtifact(previousArtifactId);
    }
  };

  const changeMode = (mode: SourceMode) => {
    setUploadError("");
    setBrowserMenuOpen(false);
    if (mode === sourceMode) return;

    if (sourceMode === "local") {
      localSourceRef.current = value.artifact_id
        ? value
        : {
            ...value,
            source_type: "path",
            storage: "local_path",
            path: pathDraft.trim(),
          };
    } else {
      minioSourceRef.current = {
        ...value,
        source_type: "minio",
        storage: "minio",
        ...parseMinioPath(pathDraft),
      };
    }

    const next =
      mode === "local" ? localSourceRef.current : minioSourceRef.current;
    setSource(next);
    setPathDraft(
      mode === "local" ? localDisplayPath(next) : minioDisplayPath(next),
    );
  };

  const commitLocalPath = () => {
    const path = pathDraft.trim();
    if (value.artifact_id && path === localDisplayPath(value)) return;
    if (!path) {
      replaceSource({ source_type: "path", storage: "local_path", path: "" });
      setUploadError("");
      return;
    }
    if (path.toLowerCase().startsWith("managed://")) {
      setUploadError("Choose the file again or enter an absolute path on the backend host.");
      return;
    }
    replaceSource({ source_type: "path", storage: "local_path", path });
    setUploadError("");
  };

  const updateMinioPath = (path: string) => {
    setPathDraft(path);
    setSource({
      ...value,
      source_type: "minio",
      storage: "minio",
      ...parseMinioPath(path),
    });
  };

  const validateUpload = (files: File[]): boolean => {
    if (!files.length) return false;
    if (files.length > MAX_DIRECTORY_FILES) {
      setUploadError(`A folder may contain at most ${MAX_DIRECTORY_FILES} files.`);
      return false;
    }
    const totalBytes = files.reduce((total, file) => total + file.size, 0);
    if (totalBytes > managedUploadMaxBytes) {
      setUploadError(
        `The selection is ${formatBytes(totalBytes)}. The maximum browser upload size is ${formatBytes(managedUploadMaxBytes)}. Use a service-visible path or MinIO for larger models.`,
      );
      return false;
    }
    return true;
  };

  const uploadSelection = async (files: File[], directory = false) => {
    if (!validateUpload(files)) return;
    setUploading(true);
    setBrowserMenuOpen(false);
    setUploadError("");
    setUploadProgress(0);
    setUploadStatus(directory ? "Uploading folder for streamed ZIP creation…" : "Uploading model artifact…");

    const form = new FormData();
    if (workflowId) form.append("workflow_id", workflowId);
    if (nodeId) form.append("node_id", nodeId);
    let endpoint: string = API_ENDPOINTS.MODEL_ARTIFACTS.UPLOAD;
    if (directory) {
      endpoint = API_ENDPOINTS.MODEL_ARTIFACTS.UPLOAD_DIRECTORY;
      const browserFiles = files as BrowserFile[];
      const relativePaths = browserFiles.map((file) => file.webkitRelativePath || file.name);
      const rootName = relativePaths[0]?.split("/")[0] || "model-folder";
      files.forEach((file) => form.append("files", file, file.name));
      form.append("paths", JSON.stringify(relativePaths));
      form.append("archive_name", `${rootName}.zip`);
    } else {
      form.append("file", files[0]);
    }

    try {
      const artifact = await apiClient.post<Record<string, any>>(endpoint, form, {
        timeout: 60 * 60 * 1000,
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event: { loaded: number; total?: number }) => {
          if (!event.total) return;
          const progress = Math.min(100, Math.round((event.loaded / event.total) * 100));
          setUploadProgress(progress);
          setUploadStatus(
            progress >= 100
              ? directory
                ? "Creating bounded ZIP archive on the scan service…"
                : "Finalizing managed artifact…"
              : `Uploading once… ${progress}%`,
          );
        },
      });
      replaceSource({ source_type: "local", ...artifact });
      setManagedArtifactStatus(artifact as ManagedArtifactStatus);
    } catch (error: any) {
      setUploadError(error?.message || "Model artifact upload failed.");
    } finally {
      setUploading(false);
      setUploadStatus("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (directoryInputRef.current) directoryInputRef.current.value = "";
    }
  };

  return (
    <div className="col-span-2 space-y-4">
      <FieldLabel label={property.displayName} helpText={getFieldHelpText(property)} />

      <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-slate-700 bg-slate-900/70 p-1">
        <button
          type="button"
          disabled={uploading}
          onClick={() => changeMode("local")}
          className={`flex items-center justify-center gap-2 rounded-md px-3 py-2.5 text-xs font-semibold transition-colors ${
            sourceMode === "local"
              ? "bg-blue-500 text-white shadow"
              : "text-slate-400 hover:bg-slate-800 hover:text-white"
          }`}
        >
          <FolderOpen size={15} />
          Local / Shared Path
        </button>
        <button
          type="button"
          disabled={uploading}
          onClick={() => changeMode("minio")}
          className={`flex items-center justify-center gap-2 rounded-md px-3 py-2.5 text-xs font-semibold transition-colors ${
            sourceMode === "minio"
              ? "bg-blue-500 text-white shadow"
              : "text-slate-400 hover:bg-slate-800 hover:text-white"
          }`}
        >
          <Database size={15} />
          MinIO
        </button>
      </div>

      {sourceMode === "local" ? (
        <div className="space-y-3">
          <div className="flex items-stretch" ref={menuRef}>
            <input
              className={inputClass}
              value={pathDraft}
              disabled={uploading}
              onChange={(event) => setPathDraft(event.target.value)}
              onBlur={commitLocalPath}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  commitLocalPath();
                }
              }}
              placeholder="Absolute file or folder path visible to the scan service"
              autoComplete="off"
              spellCheck={false}
            />
            <div className="relative shrink-0">
              <button
                type="button"
                disabled={uploading}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => setBrowserMenuOpen((open) => !open)}
                className="flex h-full items-center gap-2 rounded-r-lg border border-blue-500 bg-blue-500 px-4 text-xs font-semibold text-white hover:bg-blue-400 disabled:cursor-wait disabled:opacity-60"
              >
                {uploading ? <Loader2 className="animate-spin" size={16} /> : <FolderOpen size={16} />}
                Select
                <ChevronDown size={14} />
              </button>
              {browserMenuOpen && (
                <div className="absolute right-0 top-full z-50 mt-1 w-56 overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-xl shadow-black/40">
                  <button
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => fileInputRef.current?.click()}
                    className="flex w-full items-center gap-3 px-3 py-3 text-left text-xs text-slate-200 hover:bg-slate-800"
                  >
                    <FileArchive size={16} className="text-blue-400" />
                    Upload model file or ZIP
                  </button>
                  <button
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => directoryInputRef.current?.click()}
                    className="flex w-full items-center gap-3 px-3 py-3 text-left text-xs text-slate-200 hover:bg-slate-800"
                  >
                    <FolderOpen size={16} className="text-blue-400" />
                    Upload folder
                  </button>
                  {(value.artifact_id || value.path) && (
                    <button
                      type="button"
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => {
                        setBrowserMenuOpen(false);
                        setPathDraft("");
                        replaceSource({ source_type: "path", storage: "local_path", path: "" });
                      }}
                      className="flex w-full items-center gap-3 border-t border-slate-800 px-3 py-3 text-left text-xs text-red-300 hover:bg-red-950/40"
                    >
                      <Trash2 size={16} />
                      Clear selection
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept={modelAcceptedFiles}
            className="hidden"
            onChange={(event) => void uploadSelection(Array.from(event.target.files || []))}
          />
          <input
            ref={directoryInputRef}
            type="file"
            multiple
            className="hidden"
            {...({ webkitdirectory: "", directory: "" } as any)}
            onChange={(event) => void uploadSelection(Array.from(event.target.files || []), true)}
          />

          {uploading && (
            <div className="rounded-lg border border-blue-700/60 bg-blue-950/30 p-3">
              <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                <span className="text-blue-200">{uploadStatus}</span>
                <span className="font-semibold text-blue-300">{uploadProgress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full bg-blue-500 transition-[width] duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}
          {uploadError && <p className="text-xs text-red-400">{uploadError}</p>}
          {value.storage === "managed" && value.artifact_id && (
            <div
              className={`flex items-start gap-2 rounded-lg border p-3 text-xs leading-relaxed ${
                artifactExpired || artifactUnavailable
                  ? "border-red-800/70 bg-red-950/30 text-red-300"
                  : "border-amber-700/60 bg-amber-950/20 text-amber-200"
              }`}
            >
              <Clock3 className="mt-0.5 shrink-0" size={15} />
              <span>
                {artifactExpired || artifactUnavailable ? (
                  <>This temporary browser upload has expired. Select it again before running the workflow.</>
                ) : (
                  <>
                    Temporary browser upload. It is retained for up to {formatDuration(managedRetentionSeconds)}
                    {effectiveExpiresAt
                      ? ` (until ${new Date(effectiveExpiresAt).toLocaleString()})`
                      : ""}
                    , then for {formatDuration(postScanRetentionSeconds)} after a scan for retries. Disk-pressure
                    cleanup may remove it earlier. Use a shared path or MinIO for repeatable workflows.
                  </>
                )}
              </span>
            </div>
          )}
          <p className="text-xs leading-relaxed text-slate-500">
            An absolute service-visible path is scanned in place without copying; files, ZIPs, and
            directories are supported. Paths must be under an administrator-approved model root.
            Browser security does not expose a usable operating-system path, so Select is an ad-hoc
            upload fallback; uploaded folders become a bounded temporary ZIP with automatic retention cleanup. Browser upload: {formatBytes(managedUploadMaxBytes)}
            {artifactMaxBytes ? ` · Local/MinIO admission: ${formatBytes(artifactMaxBytes)}` : ""}
            {scannerVersion ? ` · LLM model scanner v${scannerVersion}` : ""}.
          </p>
        </div>
      ) : (
        <div className="space-y-3 rounded-xl border border-slate-700 bg-slate-900/40 p-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">MinIO credential</label>
            <CredentialSelector
              value={value.credential_id || ""}
              onChange={(credentialId) => setSource({ ...value, credential_id: credentialId })}
              serviceType="minio"
              placeholder="Select a MinIO credential"
              showCreateNew
              includeGenericFallback={false}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-300">Object path</label>
            <input
              className="w-full rounded-lg border border-slate-600 bg-[#10182c] px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
              value={pathDraft}
              onChange={(event) => updateMinioPath(event.target.value)}
              placeholder="bucket-name/models/model.zip"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
          <p className="text-xs leading-relaxed text-slate-500">
            Enter one path as bucket/object-key. Only the credential ID is stored in the workflow;
            the model is streamed from MinIO to bounded temporary disk during the scan.
          </p>
        </div>
      )}
    </div>
  );
}
