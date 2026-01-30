import React, { useState } from "react";
import Icon, { Pencil, Trash } from "../common/Icon";
import { timeAgo } from "~/lib/dateFormatter";
import { getServiceDefinition } from "~/types/credentials";
import type { UserCredential } from "~/types/api";

interface CredentialCardProps {
  credential: UserCredential;
  onEdit: (credential: UserCredential) => void;
  onDelete: (id: string) => void;
}

const CredentialCard: React.FC<CredentialCardProps> = ({
  credential,
  onEdit,
  onDelete,
}) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const serviceDefinition = getServiceDefinition(credential.service_type);
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-all duration-200">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 flex items-center justify-center">
            <Icon 
              name={credential.service_type} 
              className="w-6 h-6 object-contain"
              alt={`${serviceDefinition?.name || credential.service_type} logo`}
            />
          </div>
          <div>
            <h3 className="text-base font-semibold text-gray-900 leading-tight">
              {credential.name}
            </h3>
            <p className="text-xs text-gray-500">
              {serviceDefinition?.name || credential.service_type}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`inline-flex px-2.5 py-0.5 text-[10px] font-semibold rounded-full ${serviceDefinition?.color
              ? `bg-gradient-to-r ${serviceDefinition.color} text-white`
              : "bg-gray-100 text-gray-800"
              }`}
          >
            {serviceDefinition?.category === "ai"
              ? `${serviceDefinition?.name || credential.service_type} AI`
              : serviceDefinition?.category || credential.service_type}
          </span>
        </div>
      </div>

      {/* Metadata */}
      <div className="flex items-center gap-3 text-xs text-gray-500 mb-3">
        <span>Created: {timeAgo(credential.created_at)}</span>
        <span>Updated: {timeAgo(credential.updated_at)}</span>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-1.5">
        <button
          onClick={() => onEdit(credential)}
          className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-all duration-200"
          title="Edit credential"
        >
          <Pencil className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={() => setShowDeleteConfirm(true)}
          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-all duration-200"
          title="Delete credential"
        >
          <Trash className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-5 max-w-sm mx-4">
            <h3 className="text-base font-bold mb-3">Delete Credential</h3>
            <p className="text-gray-600 mb-5 text-sm">
              Are you sure you want to delete <strong>{credential.name}</strong>
              ? This action cannot be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-3 py-1.5 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onDelete(credential.id);
                  setShowDeleteConfirm(false);
                }}
                className="px-3 py-1.5 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CredentialCard;
