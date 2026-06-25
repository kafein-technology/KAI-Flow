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
  const dropdownRef = useRef<HTMLDivElement>(null);

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

  const handleDeleteClick = async () => {
    if (!value) return;
    const cred = userCredentials.find(c => c.id === value);
    if (!cred) return;
    
    const confirmDelete = window.confirm(`Are you sure you want to delete the credential "${cred.name}"?`);
    if (!confirmDelete) return;

    setLoadingCredential(true);
    try {
      await removeCredential(value);
      await fetchCredentials();
      onChange(""); // Clear selection
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
    : placeholder;

  return (
    <div className="space-y-3">
      {/* Custom Dropdown and Edit Button Container */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => !disabled && setDropdownOpen(!dropdownOpen)}
            disabled={disabled || loadingCredential}
            className={`w-full flex items-center justify-between bg-[#10182c] border border-slate-600 rounded-lg px-4 py-3 text-left transition-all duration-200 ${
              disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:border-slate-500"
            } ${dropdownOpen ? "border-blue-500" : ""} ${className}`}
          >
            <span className={`text-sm ${value ? "text-white" : "text-slate-400"}`}>
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
            <div className="absolute z-50 mt-1 left-0 right-0 bg-slate-900 border border-slate-700 rounded-lg shadow-lg shadow-black/40 overflow-hidden">
              {/* Credential options */}
              {filteredCredentials.map((cred) => (
                <button
                  key={cred.id}
                  type="button"
                  onClick={() => handleCredentialSelect(cred.id)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors duration-150 ${
                    value === cred.id ? "bg-blue-500/20 text-blue-300" : "text-slate-300 hover:bg-blue-500/20 hover:text-blue-300"
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
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:bg-blue-500/20 hover:text-blue-300 transition-colors duration-150 text-left border-t border-slate-700"
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
              className="p-3 bg-slate-800 border border-slate-600 hover:border-slate-500 rounded-lg text-slate-300 hover:text-white transition-all duration-200 shadow-md hover:shadow-lg flex items-center justify-center h-[46px] w-[46px]"
              title="Edit selected credential"
            >
              <Edit size={16} />
            </button>
            <button
              type="button"
              onClick={handleDeleteClick}
              className="p-3 bg-red-950/40 border border-red-900/60 hover:border-red-800 rounded-lg text-red-400 hover:text-red-300 transition-all duration-200 shadow-md hover:shadow-lg flex items-center justify-center h-[46px] w-[46px]"
              title="Delete selected credential"
            >
              <Trash2 size={16} />
            </button>
          </div>
        )}
      </div>

      {/* Service Selection Modal */}
      {showServiceSelection &&
        createPortal(
          <div className="z-[9999]">
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
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999] p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-bold text-gray-900">
                    {editingCredential
                      ? `Edit ${editingCredential.name}`
                      : `Create New ${selectedService.name} Credentials`}
                  </h2>
                  <button
                    onClick={() => {
                      setSelectedService(null);
                      setEditingCredential(null);
                      setEditingInitialValues({});
                    }}
                    className="text-gray-400 hover:text-gray-600 transition-colors"
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
          </div>,
          document.body
        )}
    </div>
  );
};

export default CredentialSelector;
