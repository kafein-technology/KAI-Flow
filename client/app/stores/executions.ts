import { create } from 'zustand';
import * as executionService from '../services/executionService';
import type { WorkflowExecution } from '../types/api';

interface ExecutionsStore {
  executions: WorkflowExecution[];
  currentExecution: WorkflowExecution | null;
  currentExecutions: Record<string, WorkflowExecution | null>; // workflow_id -> execution
  loading: boolean;
  error: string | null;
  fetchExecutions: (workflow_id?: string, params?: { skip?: number; limit?: number }) => Promise<void>;
  fetchAllExecutions: (silent?: boolean) => Promise<void>;
  getExecution: (execution_id: string) => Promise<void>;
  createExecution: (workflow_id: string, inputs: Record<string, any>) => Promise<void>;
  executeWorkflow: (workflow_id: string, executionData: {
    flow_data: any;
    input_text: string;
    node_id?: string;
    execution_type?: string;
    trigger_source?: string;
  }) => Promise<void>;
  setCurrentExecution: (execution: WorkflowExecution) => void;
  setCurrentExecutionForWorkflow: (workflow_id: string, execution: WorkflowExecution | null) => void;
  getCurrentExecutionForWorkflow: (workflow_id: string) => WorkflowExecution | null;
  deleteExecution: (execution_id: string) => Promise<void>;
  cancelExecution: (execution_id: string) => Promise<void>;
  clearError: () => void;
}

export const useExecutionsStore = create<ExecutionsStore>((set, get) => ({
  executions: [],
  currentExecution: null,
  currentExecutions: {},
  loading: false,
  error: null,
  fetchExecutions: async (workflow_id, params) => {
    if (!workflow_id) {
      set({ executions: [], loading: false, error: null });
      return;
    }
    set({ loading: true, error: null });
    try {
      const executions = await executionService.listExecutions(workflow_id, params);
      set({ executions, loading: false });
    } catch (e: any) {
      set({ error: e.message || 'Failed to fetch executions', loading: false });
    }
  },
  fetchAllExecutions: async (silent?: boolean) => {
    if (!silent) set({ loading: true, error: null });
    try {
      const executions = await executionService.listExecutions(); // call without workflow_id
      set({ executions, loading: false });
    } catch (e: any) {
      set({ error: e.message || 'Failed to fetch all executions', loading: false });
    }
  },
  getExecution: async (execution_id) => {
    set({ loading: true, error: null });
    try {
      const execution = await executionService.getExecution(execution_id);
      set({ currentExecution: execution, loading: false });
    } catch (e: any) {
      set({ error: e.message || 'Failed to fetch execution', loading: false });
    }
  },
  createExecution: async (workflow_id, inputs) => {
    set({ loading: true, error: null });
    try {
      const execution = await executionService.createExecution(workflow_id, inputs);
      set((state) => ({ executions: [execution, ...state.executions], loading: false }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to create execution', loading: false });
    }
  },
  executeWorkflow: async (workflow_id, executionData) => {
    set({ loading: true, error: null });
    try {
      const execution = await executionService.executeWorkflow(workflow_id, executionData);
      set((state) => ({
        currentExecutions: { ...state.currentExecutions, [workflow_id]: execution },
        executions: [execution, ...state.executions],
        loading: false
      }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to execute workflow', loading: false });
    }
  },
  setCurrentExecution: (execution) => {
    // Backward compatibility - set for current workflow if available
    // This is kept for legacy support but should be replaced with setCurrentExecutionForWorkflow
    console.warn('setCurrentExecution is deprecated, use setCurrentExecutionForWorkflow instead');
    set((state) => ({ currentExecutions: { ...state.currentExecutions } }));
  },
  setCurrentExecutionForWorkflow: (workflow_id, execution) => {
    set((state) => ({
      currentExecutions: { ...state.currentExecutions, [workflow_id]: execution }
    }));
  },
  getCurrentExecutionForWorkflow: (workflow_id) => {
    return get().currentExecutions[workflow_id] || null;
  },
  deleteExecution: async (execution_id) => {
    set({ loading: true, error: null });
    try {
      await executionService.deleteExecution(execution_id);
      set((state) => ({
        executions: state.executions.filter(ex => ex.id !== execution_id),
        loading: false
      }));
    } catch (e: any) {
      set({ error: e.message || 'Failed to delete execution', loading: false });
    }
  },
  cancelExecution: async (execution_id) => {
    set({ loading: true, error: null });
    try {
      const updatedExecution = await executionService.cancelExecution(execution_id);
      set((state) => {
        const nextCurrentExecutions = { ...state.currentExecutions };
        const wfId = updatedExecution.workflow_id;
        if (wfId && nextCurrentExecutions[wfId] && nextCurrentExecutions[wfId]?.id === execution_id) {
          nextCurrentExecutions[wfId] = updatedExecution;
        }
        return {
          executions: state.executions.map(ex => ex.id === execution_id ? updatedExecution : ex),
          currentExecutions: nextCurrentExecutions,
          loading: false
        };
      });
    } catch (e: any) {
      set({ error: e.message || 'Failed to cancel execution', loading: false });
      throw e;
    }
  },
  clearError: () => set({ error: null }),
})); 