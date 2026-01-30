import React, { useState, useEffect } from 'react';
import { X, Eye, Loader, AlertCircle, Globe, MessageCircle, Clock, Settings, Zap } from '../common/Icon';
import { externalWorkflowService } from '~/services/externalWorkflowService';
import type { ExternalWorkflowInfo } from '~/types/external-workflows';

interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    description?: string;
    [key: string]: any;
  };
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
}

interface WorkflowStructure {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  nodes_count: number;
  edges_count: number;
  llm_nodes: WorkflowNode[];
  memory_nodes: WorkflowNode[];
  memory_enabled: boolean;
}

interface ExternalWorkflowViewerProps {
  workflow: ExternalWorkflowInfo;
  isOpen: boolean;
  onClose: () => void;
}

export default function ExternalWorkflowViewer({ workflow, isOpen, onClose }: ExternalWorkflowViewerProps) {
  const [workflowStructure, setWorkflowStructure] = useState<WorkflowStructure | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && workflow) {
      loadWorkflowStructure();
    }
  }, [isOpen, workflow]);

  const loadWorkflowStructure = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await externalWorkflowService.getExternalWorkflowInfo(workflow.workflow_id);
      setWorkflowStructure(response.workflow_structure);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflow structure');
    } finally {
      setLoading(false);
    }
  };

  const getNodeIcon = (nodeType: string) => {
    if (nodeType.toLowerCase().includes('openai') || nodeType.toLowerCase().includes('chat')) {
      return <MessageCircle className="w-4 h-4" />;
    }
    if (nodeType.toLowerCase().includes('memory')) {
      return <Clock className="w-4 h-4" />;
    }
    if (nodeType.toLowerCase().includes('trigger') || nodeType.toLowerCase().includes('start')) {
      return <Zap className="w-4 h-4" />;
    }
    return <Settings className="w-4 h-4" />;
  };

  const getNodeColor = (nodeType: string) => {
    if (nodeType.toLowerCase().includes('openai') || nodeType.toLowerCase().includes('chat')) {
      return 'bg-blue-100 border-blue-300 text-blue-800';
    }
    if (nodeType.toLowerCase().includes('memory')) {
      return 'bg-purple-100 border-purple-300 text-purple-800';
    }
    if (nodeType.toLowerCase().includes('trigger') || nodeType.toLowerCase().includes('start')) {
      return 'bg-green-100 border-green-300 text-green-800';
    }
    return 'bg-gray-100 border-gray-300 text-gray-800';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl w-full max-w-6xl mx-4 h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Eye className="w-6 h-6 text-blue-600" />
              <h2 className="text-xl font-bold text-gray-900">Workflow Structure</h2>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Globe className="w-4 h-4" />
              <span className="font-mono bg-gray-100 px-2 py-1 rounded text-xs">
                {workflow.external_url}
              </span>
            </div>
          </div>
          
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Workflow Info */}
        <div className="p-6 border-b bg-gray-50">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">{workflow.name}</h3>
          {workflow.description && (
            <p className="text-gray-600 mb-3">{workflow.description}</p>
          )}
          
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1">
              <div className={`w-2 h-2 rounded-full ${
                workflow.connection_status === 'online' ? 'bg-green-500' : 'bg-red-500'
              }`} />
              <span className="text-gray-600">Status: </span>
              <span className={`font-medium ${
                workflow.connection_status === 'online' ? 'text-green-600' : 'text-red-600'
              }`}>
                {workflow.connection_status}
              </span>
            </div>
            
            {workflowStructure && (
              <>
                <span className="text-gray-400">•</span>
                <span className="text-gray-600">
                  {workflowStructure.nodes_count} nodes, {workflowStructure.edges_count} connections
                </span>
              </>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-3">
                <Loader className="w-8 h-8 animate-spin text-blue-600" />
                <p className="text-gray-600">Loading workflow structure...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to Load Workflow</h3>
                <p className="text-gray-600 mb-4">{error}</p>
                <button
                  onClick={loadWorkflowStructure}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Retry
                </button>
              </div>
            </div>
          ) : workflowStructure ? (
            <div className="h-full flex">
              {/* Node List */}
              <div className="w-80 border-r bg-gray-50 overflow-y-auto">
                <div className="p-4">
                  <h4 className="font-medium text-gray-900 mb-3">Workflow Nodes</h4>
                  
                  {/* Capabilities Summary */}
                  <div className="mb-4 p-3 bg-white rounded-lg border">
                    <h5 className="text-sm font-medium text-gray-700 mb-2">Capabilities</h5>
                    <div className="flex flex-wrap gap-1">
                      {workflow.capabilities?.chat && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                          <MessageCircle className="w-3 h-3" />
                          Chat
                        </span>
                      )}
                      {workflow.capabilities?.memory && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-purple-100 text-purple-800 rounded-full">
                          <Clock className="w-3 h-3" />
                          Memory
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-gray-100 text-gray-800 rounded-full">
                        <Eye className="w-3 h-3" />
                        Read-Only
                      </span>
                    </div>
                  </div>

                  {/* Nodes List */}
                  <div className="space-y-2">
                    {workflowStructure.nodes.map((node, index) => (
                      <div
                        key={node.id}
                        className={`p-3 rounded-lg border-2 ${getNodeColor(node.type)} transition-all cursor-default`}
                      >
                        <div className="flex items-start gap-2">
                          {getNodeIcon(node.type)}
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-sm truncate">
                              {node.data.label || `Node ${index + 1}`}
                            </div>
                            <div className="text-xs opacity-75 mt-1">
                              Type: {node.type}
                            </div>
                            {node.data.description && (
                              <div className="text-xs opacity-75 mt-1 line-clamp-2">
                                {node.data.description}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Visual Flow Representation */}
              <div className="flex-1 p-6 overflow-auto">
                <div className="text-center">
                  <div className="inline-block p-8 bg-gray-100 rounded-2xl">
                    <div className="w-64 h-48 bg-white rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center mb-4">
                      <div className="text-center text-gray-500">
                        <Settings className="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p className="text-sm">Workflow Visual View</p>
                        <p className="text-xs mt-1">
                          {workflowStructure.nodes_count} nodes connected with {workflowStructure.edges_count} edges
                        </p>
                      </div>
                    </div>
                    
                    <div className="text-sm text-gray-600">
                      <p className="font-medium mb-2">Flow Summary:</p>
                      <div className="text-left space-y-1">
                        <div>• Total Nodes: {workflowStructure.nodes_count}</div>
                        <div>• Connections: {workflowStructure.edges_count}</div>
                        <div>• LLM Nodes: {workflowStructure.llm_nodes.length}</div>
                        <div>• Memory Nodes: {workflowStructure.memory_nodes.length}</div>
                        <div>• Memory Enabled: {workflowStructure.memory_enabled ? 'Yes' : 'No'}</div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                    <p className="text-sm text-blue-800">
                      <strong>Read-Only Access:</strong> This is a view-only representation of the external workflow. 
                      You can see the structure and interact via chat, but cannot modify the workflow.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-gray-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
