import React, { useEffect, useState } from "react";
import {
  Search,
  AlertCircle,
  RefreshCw,
  Sparkles,
  Settings,
} from "~/icons/index";
import DraggableNode from "../common/DraggableNode";
import { useNodes } from "~/stores/nodes";
import { useSmartSuggestions } from "~/stores/smartSuggestions";
import RecommendedNodes from "./RecommendedNodes";
import SmartSuggestionsSettingsModal from "../modals/SmartSuggestionsSettingsModal";

// Loading Component
const LoadingNodes = () => (
  <div className="p-4 text-center">
    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-600 mx-auto mb-2"></div>
    <p className="text-sm text-gray-300">Loading nodes...</p>
  </div>
);

// Error Component
const ErrorNodes = ({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) => (
  <div className="p-4 text-center">
    <AlertCircle className="h-8 w-8 text-red-400 mx-auto mb-2" />
    <p className="text-sm text-gray-300 mb-2">{error}</p>
    <button
      onClick={onRetry}
      className="text-sm text-purple-400 hover:text-purple-300 flex items-center mx-auto"
    >
      <RefreshCw className="h-3 w-3 mr-1" />
      Retry
    </button>
  </div>
);

interface SidebarProps {
  onClose?: () => void;
}

function Sidebar({ onClose }: SidebarProps) {
  const {
    nodes,
    categories,
    filteredNodes,
    selectedCategory,
    searchQuery,
    isLoading,
    error,
    fetchNodes,
    fetchCategories,
    filterByCategory,
    searchNodes,
    clearError,
  } = useNodes();

  const { updateRecommendations, isEnabled, toggleEnabled, setLastAddedNode } =
    useSmartSuggestions();

  const [localSearchQuery, setLocalSearchQuery] = useState("");
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  // Fetch nodes and categories on component mount
  useEffect(() => {
    fetchNodes();
    fetchCategories();
  }, [fetchNodes, fetchCategories]);

  // Update recommendations when nodes change
  useEffect(() => {
    if (nodes.length > 0) {
      updateRecommendations(nodes);
    }
  }, [nodes, updateRecommendations]);

  // Handle search with debouncing
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      searchNodes(localSearchQuery);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [localSearchQuery, searchNodes]);

  const handleRetry = () => {
    clearError();
    fetchNodes();
    fetchCategories();
  };

  // Convert backend node metadata to draggable node format
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

  // Ensure filteredNodes is an array before mapping
  const nodesToDisplay = Array.isArray(filteredNodes)
    ? filteredNodes.map(convertToNodeType)
    : [];

  // Group nodes by category
  const nodesByCategory = nodesToDisplay.reduce((acc, node) => {
    const category = node.category || "Other";
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(node);
    return acc;
  }, {} as Record<string, any[]>);

  return (
    <div className="fixed top-36 h-[calc(100vh-12rem)] w-100 bg-[#18181A] overflow-y-auto z-30 shadow-2xl animate-slide-in rounded-2xl">
      {/* Header */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-gray-100">Add Nodes</h3>

          <div className="flex items-center gap-2">
            {/* Smart Suggestions Settings */}
            <button
              onClick={() => setShowSettingsModal(true)}
              className="p-1 text-gray-400 hover:text-white transition-colors"
              title="Smart Suggestions Settings"
            >
              <Settings className="h-4 w-4 brightness-0 invert" />
            </button>

            {/* Smart Suggestions Toggle */}
            <button
              onClick={toggleEnabled}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${isEnabled
                  ? "bg-yellow-500/20 text-yellow-400 border border-yellow-400/30"
                  : "bg-gray-700 text-gray-400 border border-gray-600"
                }`}
              title={
                isEnabled
                  ? "Disable Smart Suggestions"
                  : "Enable Smart Suggestions"
              }
            >
              <Sparkles className="h-3 w-3 brightness-0 invert" />
              <span>Smart</span>
            </button>
          </div>
        </div>

        {/* Search Input */}
        <label className="input w-full rounded-2xl bg-transparent text-gray-100 border border-gray-600 flex items-center gap-2 px-2 py-1 mb-3 focus-within:border-purple-400">
          <Search className="h-4 w-4 brightness-0 invert opacity-50" />
          <input
            type="search"
            className="grow bg-transparent text-gray-100 placeholder-gray-400 focus:outline-none"
            placeholder="Search nodes..."
            value={localSearchQuery}
            onChange={(e) => setLocalSearchQuery(e.target.value)}
          />
        </label>
      </div>

      {/* Content */}
      <div className="p-3">
        {error ? (
          <ErrorNodes error={error} onRetry={handleRetry} />
        ) : isLoading && nodes.length === 0 ? (
          <LoadingNodes />
        ) : nodesToDisplay.length === 0 ? (
          <div className="text-center py-4">
            <p className="text-sm text-gray-300">
              {searchQuery
                ? `No nodes match "${searchQuery}"`
                : "No nodes available"}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Recommended Nodes Section */}
            <RecommendedNodes availableNodes={nodes} />

            {selectedCategory ? (
              // Show filtered nodes in current category
              <div>
                <h4 className="text-sm font-medium text-gray-200 mb-2">
                  {categories.find((c) => c.name === selectedCategory)
                    ?.display_name || selectedCategory}
                </h4>
                <div className="space-y-2">
                  {nodesToDisplay.map((nodeType) => (
                    <DraggableNode key={nodeType.id} nodeType={nodeType} icon={nodeType.data.icon} />
                  ))}
                </div>
              </div>
            ) : (
              // Show nodes grouped by category
              Object.entries(nodesByCategory).map(
                ([categoryName, categoryNodes]) => (
                  <div
                    key={categoryName}
                    className="collapse collapse-arrow rounded-lg bg-gray-800/30 border border-gray-700"
                  >
                    <input type="checkbox" defaultChecked />
                    <div className="collapse-title font-semibold text-sm text-gray-200">
                      {categories.find((c) => c.name === categoryName)
                        ?.display_name || categoryName}
                      <span className="ml-2 text-xs text-gray-400">
                        ({categoryNodes.length})
                      </span>
                    </div>
                    <div className="collapse-content space-y-2">
                      {categoryNodes.map((nodeType) => (
                        <React.Fragment key={nodeType.id}>
                          <DraggableNode nodeType={nodeType} icon={nodeType.data.icon} />
                          <hr className="my-2 border-gray-600" />
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                )
              )
            )}

            {/* Results summary */}
            {(searchQuery || selectedCategory) && (
              <div className="text-xs text-gray-400 pt-2 border-t border-gray-600">
                Showing {nodesToDisplay.length} of {nodes.length} nodes
              </div>
            )}
          </div>
        )}
      </div>

      {/* Smart Suggestions Settings Modal */}
      <SmartSuggestionsSettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
      />
    </div>
  );
}

export default Sidebar;
