import React, { useState } from "react";
import { ExternalLink, Loader2, Search } from "lucide-react";
import { Link } from "react-router";
import { timeAgo } from "~/lib/dateFormatter";
import type { CredentialWorkflowUsageResponse } from "~/types/api";

interface CredentialWorkflowUsageProps {
  usage: CredentialWorkflowUsageResponse | null;
  isLoading: boolean;
  error: string | null;
  isOpen: boolean;
}

const CredentialWorkflowUsage: React.FC<CredentialWorkflowUsageProps> = ({
  usage,
  isLoading,
  error,
  isOpen,
}) => {
  const [searchTerm, setSearchTerm] = useState("");

  // Hide component while loading or when not open
  if (!isOpen || isLoading) return null;

  const count = usage?.workflow_count ?? 0;

  // Filter workflows by search term
  const filteredWorkflows = usage?.workflows.filter((w) =>
    w.name.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className="mt-3 pt-3 border-t border-gray-100 space-y-2.5 animate-in slide-in-from-top-2 duration-200">
      {error ? (
        <p className="text-xs text-red-500 py-0.5">{error}</p>
      ) : count === 0 ? (
        <p className="text-xs text-gray-500 py-0.5">Not used in any workflow</p>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
              Used in workflows ({count})
            </span>
          </div>

          {/* Search Input for 5+ workflows */}
          {count > 5 && (
            <div className="relative">
              <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-3 w-3 text-gray-400" />
              <input
                type="text"
                placeholder="Search workflows..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-7 pr-3 py-1 text-xs border border-gray-200 rounded-md focus:ring-1 focus:ring-blue-500 focus:border-transparent outline-none bg-gray-50/50"
              />
            </div>
          )}

          {/* Workflows List */}
          {filteredWorkflows.length === 0 ? (
            <p className="text-xs text-gray-400 py-1 text-center">No matching workflows found</p>
          ) : (
            <ul className="space-y-1.5 max-h-36 overflow-y-auto pr-1 scrollbar-thin">
              {filteredWorkflows.map((workflow) => {
                const primaryNode = workflow.using_nodes[0];
                const extraNodes = workflow.using_nodes.length - 1;

                return (
                  <li
                    key={workflow.id}
                    className="flex items-start justify-between gap-2 text-xs py-1 hover:bg-gray-50 rounded px-1.5 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/canvas?workflow=${workflow.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-blue-600 hover:text-blue-800 hover:underline truncate block"
                      >
                        {workflow.name}
                      </Link>
                      <p className="text-[10px] text-gray-400 mt-0.5">
                        {primaryNode?.node_type || "Node"}
                        {extraNodes > 0 ? ` (+${extraNodes})` : ""}
                        {" · "}
                        updated {timeAgo(workflow.updated_at)}
                      </p>
                    </div>
                    <Link
                      to={`/canvas?workflow=${workflow.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 p-0.5 text-gray-400 hover:text-blue-600 transition-colors"
                      title="Open workflow"
                    >
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </div>
  );
};

export default CredentialWorkflowUsage;
