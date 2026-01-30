import React from "react";
import { Sparkles } from "./Icon";
import DraggableNode from "./DraggableNode";
import { useSmartSuggestions } from "~/stores/smartSuggestions";
import { SmartSuggestionsService } from "~/services/smartSuggestions";

interface RecommendedNodesProps {
  availableNodes: any[];
}

const RecommendedNodes: React.FC<RecommendedNodesProps> = ({
  availableNodes,
}) => {
  const { recommendedNodes, lastAddedNode, isEnabled } = useSmartSuggestions();

  // If smart suggestions are disabled or no recommendations, don't render
  if (!isEnabled || recommendedNodes.length === 0) {
    return null;
  }

  const chainDescription = lastAddedNode
    ? SmartSuggestionsService.getChainDescription(lastAddedNode)
    : null;

  const chainCategory = lastAddedNode
    ? SmartSuggestionsService.getChainCategory(lastAddedNode)
    : null;

  // Convert recommended nodes to the format expected by DraggableNode
  const convertToNodeType = (nodeMetadata: any) => ({
    id: nodeMetadata.name,
    type: nodeMetadata.name,
    name: nodeMetadata.name,
    display_name: nodeMetadata.display_name,
    category: nodeMetadata.category,
    data: {
      name: nodeMetadata.name,
      displayName: nodeMetadata.display_name,
      description: nodeMetadata.description,
      inputs: nodeMetadata.inputs,
      outputs: nodeMetadata.outputs,
      icon: nodeMetadata.icon,
      color: nodeMetadata.color,
    },
    info: nodeMetadata.description,
  });

  const recommendedNodeTypes = recommendedNodes.map(convertToNodeType);

  return (
    <div className="mb-4">
      {/* Recommended Header */}
      <div className="flex items-center gap-2 mb-3 px-2">
        <Sparkles className="h-4 w-4 text-yellow-400" />
        <h4 className="text-sm font-semibold text-yellow-400">Recommended</h4>
        {chainCategory && (
          <span className="text-xs text-gray-400 bg-gray-700 px-2 py-1 rounded">
            {chainCategory}
          </span>
        )}
      </div>

      {/* Description */}
      {chainDescription && (
        <p className="text-xs text-gray-400 mb-3 px-2">{chainDescription}</p>
      )}

      {/* Recommended Nodes */}
      <div className="space-y-2">
        {recommendedNodeTypes.map((nodeType) => (
          <div key={nodeType.id} className="relative">
            <DraggableNode nodeType={nodeType} />
            {/* Highlight effect */}
            <div className="absolute inset-0 bg-yellow-400/10 rounded-lg pointer-events-none border border-yellow-400/20" />
          </div>
        ))}
      </div>

      {/* Divider */}
      <div className="border-t border-gray-600 my-4" />
    </div>
  );
};

export default RecommendedNodes;
