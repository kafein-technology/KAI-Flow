import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Loader2Icon as Loader2 } from "../../icons/index";
import { useUserCredentialStore } from "~/stores/userCredential";
import { getUserCredentialById } from "~/services/userCredentialService";
import ServiceSelectionModal from "~/components/credentials/ServiceSelectionModal";
import DynamicCredentialForm from "~/components/credentials/DynamicCredentialForm";
import type { ServiceDefinition } from "~/types/credentials";
import { getServiceDefinition } from "~/types/credentials";

interface CredentialSelectorProps {
  value: string | undefined;
  onChange: (credentialId: string) => void;
  onCredentialLoad?: (credential: any) => void;
  serviceType?: string; // Optional: filter credentials by service type
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
  placeholder = "Choose a credential...",
  disabled = false,
  className = "",
  showCreateNew = true,
  includeGenericFallback = true,
}) => {
  const { userCredentials, addCredential, fetchCredentials, isLoading } =
    useUserCredentialStore();
  const [loadingCredential, setLoadingCredential] = useState(false);
  const [showServiceSelection, setShowServiceSelection] = useState(false);
  const [selectedService, setSelectedService] =
    useState<ServiceDefinition | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const predefinedService: ServiceDefinition | null = serviceType
    ? getServiceDefinition(serviceType) || null
    : null;

  // Ensure credentials are fetched
  useEffect(() => {
    if (!userCredentials || userCredentials.length === 0) {
      fetchCredentials();
    }
  }, [fetchCredentials]);

  // Filter credentials by service type if specified
  const filteredCredentials = serviceType
    ? userCredentials.filter((cred) => {
        if (cred.service_type === serviceType) return true;
        if (includeGenericFallback && cred.service_type === "generic_api") {
          return true;
        }
        return false;
      })
    : userCredentials;

  const handleCredentialSelect = async (credentialId: string) => {
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
        data: values,
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

  const hasCredentials = filteredCredentials.length > 0;
  const showCreateButton = showCreateNew && !hasCredentials;

  const CREATE_NEW_VALUE = "__create_new__";

  return (
    <div className="space-y-3">
      {/* Credential Selection */}
      <div className="relative">
        <select
          className={`w-full bg-slate-900/80 border border-slate-600/50 rounded-lg 
            text-white p-3 focus:border-emerald-500 focus:ring-2 
            focus:ring-emerald-500/20 transition-all ${className}`}
          value={value}
          onChange={(e) => {
            const selected = e.target.value;
            if (selected === CREATE_NEW_VALUE) {
              // Revert selection and open creation flow
              e.currentTarget.value = value || "";
              if (predefinedService) {
                setSelectedService(predefinedService);
              } else {
                setShowServiceSelection(true);
              }
              return;
            }
            handleCredentialSelect(selected);
          }}
          disabled={disabled || loadingCredential}
        >
          <option value="">{placeholder}</option>
          {filteredCredentials.map((cred) => (
            <option key={cred.id} value={cred.id}>
              {cred.name} ({cred.service_type})
            </option>
          ))}
          {showCreateNew && (
            <option value={CREATE_NEW_VALUE}>
              ➕{" "}
              {predefinedService
                ? `Create new ${predefinedService.name} credentials…`
                : "Create new credentials…"}
            </option>
          )}
        </select>

        {loadingCredential && (
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
            <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
          </div>
        )}
      </div>

      {/* Note: 'Create new' entry moved into select as an option */}

      {/* Service Selection Modal */}
      {showServiceSelection &&
        createPortal(
          <div className="z-[9999]">
            <ServiceSelectionModal
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
                    Create New {selectedService.name} Credentials
                  </h2>
                  <button
                    onClick={() => setSelectedService(null)}
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
                  onSubmit={handleCreateCredential}
                  onCancel={() => setSelectedService(null)}
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
