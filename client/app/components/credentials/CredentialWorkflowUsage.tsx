import React from "react";
import { ExternalLink, GitBranch, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { timeAgo } from "~/lib/dateFormatter";
import type { CredentialWorkflowUsageResponse } from "~/types/api";

interface CredentialWorkflowUsageProps {
  usage: CredentialWorkflowUsageResponse | null;
  isLoading: boolean;
  error: string | null;
}

const CredentialWorkflowUsage: React.FC<CredentialWorkflowUsageProps> = ({
  usage,
  isLoading,
  error,
}) => {
  if (isLoading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading workflow usage...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  if (!usage) {
    return null;
  }

  const count = usage.workflow_count;

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 space-y-3">
      <div className="flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-purple-600" />
        <h4 className="text-sm font-semibold text-gray-900">
          Used in {count} workflow{count === 1 ? "" : "s"}
        </h4>
      </div>

      {count === 0 ? (
        <p className="text-sm text-gray-500">Not used in any workflow</p>
      ) : (
        <ul className="space-y-2">
          {usage.workflows.map((workflow) => {
            const primaryNode = workflow.using_nodes[0];
            const extraNodes = workflow.using_nodes.length - 1;

            return (
              <li
                key={workflow.id}
                className="rounded-md border border-gray-200 bg-white px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <Link
                      to={`/canvas?workflow=${workflow.id}`}
                      className="text-sm font-medium text-purple-700 hover:text-purple-900 hover:underline truncate block"
                    >
                      {workflow.name}
                    </Link>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {primaryNode?.node_type || "Node"}
                      {extraNodes > 0
                        ? ` · +${extraNodes} more node${extraNodes === 1 ? "" : "s"}`
                        : ""}
                      {" · "}
                      updated {timeAgo(workflow.updated_at)}
                    </p>
                  </div>
                  <Link
                    to={`/canvas?workflow=${workflow.id}`}
                    className="shrink-0 p-1 text-gray-400 hover:text-purple-600"
                    title="Open workflow"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default CredentialWorkflowUsage;
