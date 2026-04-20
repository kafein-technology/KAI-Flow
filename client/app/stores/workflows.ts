import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import WorkflowService from '~/services/workflows';
import type {
  Workflow,
  WorkflowCreateRequest,
  WorkflowUpdateRequest,
  WorkflowData,
  WorkflowTemplate,
  WorkflowTemplateCreate,
  WorkflowTemplateResponse,
  WorkflowStats,
} from '~/types/api';
import type { StateCreator } from 'zustand'
interface WorkflowState {
  workflows: Workflow[];
  publicWorkflows: Workflow[];
  templates: WorkflowTemplateResponse[];
  categories: string[];
  dashboardStats: WorkflowStats | null;
  currentWorkflow: Workflow | null;
  isLoading: boolean;
  error: string | null;
  hasUnsavedChanges: boolean;
  // Actions
  fetchWorkflows: () => Promise<void>;
  fetchPublicWorkflows: () => Promise<void>;
  fetchWorkflow: (id: string) => Promise<void>;
  createWorkflow: (data: WorkflowCreateRequest) => Promise<Workflow>;
  updateWorkflow: (id: string, data: WorkflowUpdateRequest) => Promise<void>;
  deleteWorkflow: (id: string) => Promise<void>;
  duplicateWorkflow: (id: string, new_name?: string) => Promise<Workflow>;
  updateWorkflowVisibility: (id: string, is_public: boolean) => Promise<void>;
  updateWorkflowStatus: (id: string, is_active: boolean) => Promise<void>;
  fetchTemplates: () => Promise<void>;
  fetchCategories: () => Promise<void>;
  createTemplate: (data: WorkflowTemplateCreate) => Promise<WorkflowTemplateResponse>;
  createTemplateFromWorkflow: (workflow_id: string, template_name: string, template_description?: string, category?: string) => Promise<WorkflowTemplateResponse>;
  fetchDashboardStats: () => Promise<void>;
  setCurrentWorkflow: (workflow: Workflow | null) => void;
  setHasUnsavedChanges: (hasChanges: boolean) => void;
  clearError: () => void;
}

const workflowStateCreator: StateCreator<WorkflowState> = (set, get) => ({
  workflows: [],
  publicWorkflows: [],
  templates: [],
  categories: [],
  dashboardStats: null,
  currentWorkflow: null,
  isLoading: false,
  error: null,
  hasUnsavedChanges: false,
  fetchWorkflows: async () => {
    set({ isLoading: true, error: null });
    try {
      const workflows = await WorkflowService.getWorkflows();
      // Add default is_active status for workflows
      const workflowsWithStatus = workflows.map(workflow => ({
        ...workflow,
        is_active: workflow.is_active ?? true
      }));
      set({ workflows: workflowsWithStatus, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
  fetchPublicWorkflows: async () => {
    set({ isLoading: true, error: null });
    try {
      const publicWorkflows = await WorkflowService.getPublicWorkflows();
      set({ publicWorkflows, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
  fetchWorkflow: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const workflow = await WorkflowService.getWorkflow(id);
      set({ currentWorkflow: workflow, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
  createWorkflow: async (data: WorkflowCreateRequest) => {
    set({ isLoading: true });
    try {
      const newWorkflow = await WorkflowService.createWorkflow(data);
      set((state) => ({ workflows: [...state.workflows, newWorkflow], isLoading: false }));
      return newWorkflow;
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },
  updateWorkflow: async (id: string, data: WorkflowUpdateRequest) => {
    set({ isLoading: true });
    try {
      const updatedWorkflow = await WorkflowService.updateWorkflow(id, data);

      // Validate response
      if (!updatedWorkflow || !updatedWorkflow.id) {
        throw new Error("Invalid response from server");
      }

      set((state) => ({
        workflows: state.workflows.map((w) => (w.id === id ? updatedWorkflow : w)),
        currentWorkflow: state.currentWorkflow?.id === id ? updatedWorkflow : state.currentWorkflow,
        isLoading: false,
        error: null,
      }));
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || error?.message || "Failed to update workflow";
      console.error("Update workflow error:", errorMessage, error);
      set({ error: errorMessage, isLoading: false });
      throw error;
    }
  },
  deleteWorkflow: async (id: string) => {
    set({ isLoading: true });
    try {
      await WorkflowService.deleteWorkflow(id);
      set((state) => ({ workflows: state.workflows.filter((w) => w.id !== id), isLoading: false }));
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },
  duplicateWorkflow: async (id: string, new_name?: string) => {
    set({ isLoading: true });
    try {
      const duplicated = await WorkflowService.duplicateWorkflow(id, new_name);
      set((state) => ({ workflows: [...state.workflows, duplicated], isLoading: false }));
      return duplicated;
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },
  updateWorkflowVisibility: async (id: string, is_public: boolean) => {
    set({ isLoading: true });
    try {
      await WorkflowService.updateWorkflowVisibility(id, is_public);
      // Lokal state'i güncelle — UI'ın anında yansıması için
      set((state) => ({
        workflows: state.workflows.map((w) =>
          w.id === id ? { ...w, is_public } : w
        ),
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },
  updateWorkflowStatus: async (id: string, is_active: boolean) => {
    set({ isLoading: true });
    try {
      // Update local state immediately for better UX
      set((state) => ({
        workflows: state.workflows.map((w) =>
          w.id === id ? { ...w, is_active } : w
        ),
        currentWorkflow: state.currentWorkflow?.id === id
          ? { ...state.currentWorkflow, is_active }
          : state.currentWorkflow,
        isLoading: false,
      }));

      // NOTE: Using is_public for Kafka activation as per user request
      // TODO: Link this toggle to is_public if desired
      // await WorkflowService.updateWorkflow(id, { is_public: is_active });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },
  fetchTemplates: async () => {
    set({ isLoading: true });
    try {
      const templates = await WorkflowService.getWorkflowTemplates();
      set({ templates, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
  fetchCategories: async () => {
    set({ isLoading: true });
    try {
      const { categories } = await WorkflowService.getTemplateCategories();
      set({ categories, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
  createTemplate: async (data: WorkflowTemplateCreate) => {
    set({ isLoading: true });
    try {
      const template = await WorkflowService.createWorkflowTemplate(data);
      set((state) => ({ templates: [...state.templates, template], isLoading: false }));
      return template;
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },
  createTemplateFromWorkflow: async (workflow_id: string, template_name: string, template_description?: string, category?: string) => {
    set({ isLoading: true });
    try {
      const template = await WorkflowService.createTemplateFromWorkflow(workflow_id, template_name, template_description, category);
      set((state) => ({ templates: [...state.templates, template], isLoading: false }));
      return template;
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },

  fetchDashboardStats: async () => {
    set({ isLoading: true });
    try {
      const dashboardStats = await WorkflowService.getDashboardStats();
      set({ dashboardStats, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false });
    }
  },
  setCurrentWorkflow: (workflow: Workflow | null) => {
    set({ currentWorkflow: workflow, hasUnsavedChanges: false });
  },
  setHasUnsavedChanges: (hasChanges: boolean) => {
    set({ hasUnsavedChanges: hasChanges });
  },
  clearError: () => set({ error: null }),
});

export const useWorkflows = create<WorkflowState>()(
  subscribeWithSelector(workflowStateCreator),
); 