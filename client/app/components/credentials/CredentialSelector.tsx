import React, { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { Loader2, ChevronDown, Plus, Edit, Trash2 } from "lucide-react";
import { useUserCredentialStore } from "~/stores/userCredential";
import {
  getUserCredentialById,
  testCredentialRaw,
} from "~/services/userCredentialService";
import ServiceSelectionModal from "~/components/credentials/ServiceSelectionModal";
import DynamicCredentialForm from "~/components/credentials/DynamicCredentialForm";
import DeleteConfirmationModal from "~/components/modals/DeleteConfirmationModal";
import { getCredentialData } from "~/components/credentials/credentialPayload";
import type { ServiceDefinition } from "~/types/credentials";
import { getServiceDefinition } from "~/types/credentials";

interface CredentialSelectorProps {
  value: string | undefined;
  onChange: (credentialId: string) => void;
  onCredentialLoad?: (credential: any) => void;
  serviceType?: string; // Optional: filter credentials by service type
  allowedServiceTypes?: string[]; // Optional: filter credentials by multiple service types
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  showCreateNew?: boolean; // Whether to show create new credentials option
  includeGenericFallback?: boolean; // Whether to include generic_api creds alongside serviceType
  allowNone?: boolean;
  appearance?: "default" | "dark";
}

const CredentialSelector: React.FC<CredentialSelectorProps> = ({
  value,
  onChange,
  onCredentialLoad,
  serviceType,
  allowedServiceTypes,
  placeholder = "Select API Key",
  disabled = false,
  className = "",
  showCreateNew = true,
  includeGenericFallback = true,
  allowNone = false,
  appearance = "default",
}) => {
  const { userCredentials, addCredential, updateCredential, removeCredential, fetchCredentials, isLoading } =
    useUserCredentialStore();
  const [loadingCredential, setLoadingCredential] = useState(false);
  const [showServiceSelection, setShowServiceSelection] = useState(false);
  const [selectedService, setSelectedService] =
    useState<ServiceDefinition | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [editingCredential, setEditingCredential] = useState<any | null>(null);
  const [editingInitialValues, setEditingInitialValues] = useState<Record<string, any>>({});
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const isDarkAppearance = appearance === "dark";

  const predefinedService: ServiceDefinition | null = serviceType
    ? getServiceDefinition(serviceType) || null
    : null;

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Ensure credentials are fetched
  useEffect(() => {
    if (!userCredentials || userCredentials.length === 0) {
      fetchCredentials();
    }
  }, [fetchCredentials]);

  // Filter credentials by service type if specified
  const filteredCredentials = allowedServiceTypes
    ? userCredentials.filter((cred) => allowedServiceTypes.includes(cred.service_type))
    : serviceType
    ? userCredentials.filter((cred) => {
        if (cred.service_type === serviceType) return true;
        if (includeGenericFallback && cred.service_type === "generic_api") {
          return true;
        }
        return false;
      })
    : userCredentials;

  const handleCredentialSelect = async (credentialId: string) => {
    setDropdownOpen(false);

    if (!credentialId) {
      onChange("");
      if (onCredentialLoad) {
        onCredentialLoad(null);
      }
      return;
    }

    if (!onCredentialLoad) {
      onChange(credentialId);
      return;
    }

    setLoadingCredential(true);
    try {
      const result = await getUserCredentialById(credentialId);
      onChange(credentialId);

      if (onCredentialLoad && result?.secret) {
        onCredentialLoad(result.secret);
      }
    } catch (error) {
      console.error("Failed to fetch credential secret:", error);
    } finally {
      setLoadingCredential(false);
    }
  };

  const handleServiceSelect = (service: ServiceDefinition) => {
    setSelectedService(service);
    setShowServiceSelection(false);
  };

  const handleCreateCredential = async (values: Record<string, any>) => {
    if (!selectedService) return;

    setIsSubmitting(true);
    try {
      const payload = {
        name: values.name || `${selectedService.name} Credential`,
        data: getCredentialData(values),
        service_type: selectedService.id,
      };

      const newCredential = await addCredential(payload);
      // Ensure store is fresh
      await fetchCredentials();

      // Auto-select the newly created credential
      if (newCredential && newCredential.id) {
        await handleCredentialSelect(newCredential.id);
      }

      setSelectedService(null);
    } catch (error) {
      console.error("Failed to create credential:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateNewClick = () => {
    setDropdownOpen(false);
    if (predefinedService) {
      setSelectedService(predefinedService);
    } else {
      setShowServiceSelection(true);
    }
  };

  const handleEditClick = async () => {
    if (!value) return;
    const cred = userCredentials.find(c => c.id === value);
    if (!cred) return;
    
    setLoadingCredential(true);
    try {
      const detail = await getUserCredentialById(value);
      const serviceDef = getServiceDefinition(cred.service_type);
      if (serviceDef) {
        setSelectedService(serviceDef);
        setEditingCredential(cred);
        if (detail?.secret && typeof detail.secret === "object") {
          setEditingInitialValues(detail.secret);
        } else {
          setEditingInitialValues({});
        }
      }
    } catch (error) {
      console.error("Failed to fetch credential for editing:", error);
    } finally {
      setLoadingCredential(false);
    }
  };

  const handleUpdateCredential = async (values: Record<string, any>) => {
    if (!editingCredential || !selectedService) return;

    setIsSubmitting(true);
    try {
      const payload = {
        name: values.name || editingCredential.name,
        data: getCredentialData(values),
        service_type: selectedService.id,
      };

      await updateCredential(editingCredential.id, payload);
      await fetchCredentials();

      // Refresh selection details
      await handleCredentialSelect(editingCredential.id);

      setSelectedService(null);
      setEditingCredential(null);
      setEditingInitialValues({});
    } catch (error) {
      console.error("Failed to update credential:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteClick = () => {
    if (!value) return;
    const cred = userCredentials.find(c => c.id === value);
    if (!cred) return;
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    if (!value) return;
    setLoadingCredential(true);
    try {
      await removeCredential(value);
      await fetchCredentials();
      onChange(""); // Clear selection
      setShowDeleteConfirm(false);
      if (onCredentialLoad) {
        onCredentialLoad(null);
      }
    } catch (error) {
      console.error("Failed to delete credential:", error);
    } finally {
      setLoadingCredential(false);
    }
  };

  // Get selected credential name
  const selectedCredential = filteredCredentials.find(cred => cred.id === value);
  const displayText = selectedCredential
    ? `${selectedCredential.name} (${selectedCredential.service_type})`
    : value ? "Credential unavailable" : allowNone ? "None (no authentication)" : placeholder;

  return (
    <div className="space-y-3">
      {/* Custom Dropdown and Edit Button Container */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => !disabled && setDropdownOpen(!dropdownOpen)}
            disabled={disabled || loadingCredential}
            className={`w-full flex items-center justify-between rounded-lg px-4 py-3 text-left transition-all duration-200 ${
              isDarkAppearance
            ? `border bg-[var(--kai-surface-control)] text-zinc-100 ${dropdownOpen ? "border-[var(--kai-accent)] ring-1 ring-[var(--kai-accent)]/30" : "border-[var(--kai-field-border)] hover:border-[var(--kai-selector-hover-border)] hover:bg-[var(--kai-selector-hover-bg)]"}`
                : `bg-[var(--kai-node-field-bg)] border border-slate-600 ${dropdownOpen ? "border-blue-500" : ""} hover:border-slate-500`
            } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"} ${className}`}
          >
            <span className={`text-sm ${value ? "text-white" : isDarkAppearance ? "text-zinc-400" : "text-slate-400"}`}>
              {displayText}
            </span>
            <div className="flex items-center gap-2">
              {loadingCredential && (
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              )}
              <ChevronDown
                size={16}
                className={`text-slate-400 transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`}
              />
            </div>
          </button>

          {/* Dropdown Menu */}
          {dropdownOpen && (
            <div className={`absolute z-50 mt-1 left-0 right-0 rounded-lg border shadow-lg shadow-black/40 overflow-hidden ${isDarkAppearance ? "bg-[var(--kai-surface-control)] border-[var(--kai-control-border)]" : "bg-slate-900 border-slate-700"}`}>
              {allowNone && (
                <button
                  type="button"
                  onClick={() => handleCredentialSelect("")}
                  className={`w-full px-4 py-2.5 text-sm text-left transition-colors ${isDarkAppearance ? "text-zinc-200 hover:bg-[var(--kai-surface-hover)]" : "text-slate-300 hover:bg-blue-500/20"}`}
                >
                  None (no authentication)
                </button>
              )}
              {/* Credential options */}
              {filteredCredentials.map((cred) => (
                <button
                  key={cred.id}
                  type="button"
                  onClick={() => handleCredentialSelect(cred.id)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors duration-150 ${
                    isDarkAppearance
                      ? value === cred.id ? "bg-[var(--kai-accent)]/15 text-[var(--kai-accent-text-soft)]" : "text-zinc-200 hover:bg-[var(--kai-surface-hover)] hover:text-white"
                      : value === cred.id ? "bg-blue-500/20 text-blue-300" : "text-slate-300 hover:bg-blue-500/20 hover:text-blue-300"
                  }`}
                >
                  {cred.name} ({cred.service_type})
                </button>
              ))}

              {/* Create new option */}
              {showCreateNew && (
                <button
                  type="button"
                  onClick={handleCreateNewClick}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors duration-150 text-left border-t ${isDarkAppearance ? "border-[var(--kai-control-border)] text-zinc-200 hover:bg-[var(--kai-surface-hover)] hover:text-white" : "border-slate-700 text-slate-300 hover:bg-blue-500/20 hover:text-blue-300"}`}
                >
                  <Plus size={14} className="text-slate-500" />
                  {predefinedService
                    ? `Create new ${predefinedService.name} credentials…`
                    : "Create new credentials…"}
                </button>
              )}
            </div>
          )}
        </div>

        {value && !disabled && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleEditClick}
              className={`p-3 border rounded-lg transition-all duration-200 flex items-center justify-center h-[46px] w-[46px] ${isDarkAppearance ? "bg-[var(--kai-surface-control)] border-[var(--kai-field-border)] text-[var(--kai-control-accent-text)] hover:border-[var(--kai-accent)]/60 hover:bg-[var(--kai-accent)]/15 hover:text-white" : "bg-slate-800 border-slate-600 hover:border-slate-500 text-slate-300 hover:text-white shadow-md hover:shadow-lg"}`}
              title="Edit selected credential"
            >
              <Edit size={16} />
            </button>
            <button
              type="button"
              onClick={handleDeleteClick}
              className="kai-delete-trigger rounded-lg flex items-center justify-center h-[46px] w-[46px]"
              title="Delete selected credential"
            >
              <Trash2 size={16} />
            </button>
          </div>
        )}
      </div>

      {showDeleteConfirm && selectedCredential &&
        createPortal(
          <DeleteConfirmationModal
            isOpen={showDeleteConfirm}
            title="Delete Credential"
            message={`Are you sure you want to delete the credential \"${selectedCredential.name}\"?`}
            onClose={() => setShowDeleteConfirm(false)}
            onConfirm={handleDeleteConfirm}
          />,
          document.body
        )}

      {/* Service Selection Modal */}
      {showServiceSelection &&
        createPortal(
          <div className="kai-product-surface kai-portal-surface">
            <ServiceSelectionModal
              allowedServiceTypes={allowedServiceTypes}
              onSelectService={handleServiceSelect}
              onClose={() => setShowServiceSelection(false)}
            />
          </div>,
          document.body
        )}

      {/* Dynamic Credential Form Modal */}
      {selectedService &&
        createPortal(
          <div className="kai-product-surface kai-portal-surface">
            <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/70 p-4 backdrop-blur-[2px]">
              <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-[var(--kai-border-soft)] bg-[var(--kai-surface-dialog)] text-zinc-100 shadow-2xl shadow-black/50">
                <div className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-white">
                      {editingCredential
                        ? `Edit ${editingCredential.name}`
                        : `Create New ${selectedService.name} Credentials`}
                    </h2>
                    <button
                      type="button"
                      aria-label="Close credential form"
                      onClick={() => {
                        setSelectedService(null);
                        setEditingCredential(null);
                        setEditingInitialValues({});
                      }}
                      className="rounded-md p-1 text-zinc-400 transition-colors hover:bg-[var(--kai-surface-hover)] hover:text-white"
                    >
                      <svg
                        className="w-6 h-6"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>

                  <DynamicCredentialForm
                    service={selectedService}
                    onSubmit={editingCredential ? handleUpdateCredential : handleCreateCredential}
                    onCancel={() => {
                      setSelectedService(null);
                      setEditingCredential(null);
                      setEditingInitialValues({});
                    }}
                    onTest={(values) =>
                      testCredentialRaw(
                        selectedService.id,
                        getCredentialData(values)
                      )
                    }
                    initialValues={
                      editingCredential
                        ? { name: editingCredential.name, ...editingInitialValues }
                        : { name: `${selectedService.name} Credential` }
                    }
                    isSubmitting={isSubmitting}
                  />
                </div>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
};

export default CredentialSelector;
