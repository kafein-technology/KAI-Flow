import { create } from 'zustand';
import { listVariables, createVariable, getVariable, removeVariable, updateVariable } from '../services/variableService';
import type { Variable, VariableCreateRequest } from '~/types/api';

interface VariableStore {
  variables: Variable[];
  isLoading: boolean;
  error: string | null;
  fetchVariables: () => Promise<void>;
  createVariable: (data: VariableCreateRequest) => Promise<void>;
  getVariable: (id: string) => Promise<void>;
  removeVariable: (id: string) => Promise<void>;
  updateVariable: (id: string, inputs: Partial<VariableCreateRequest>) => Promise<void>;
}

export const useVariableStore = create<VariableStore>((set, get) => ({
  variables: [],
  isLoading: false,
  error: null,

  fetchVariables: async () => {
    set({ isLoading: true, error: null });
    try {
      const variables = await listVariables();
      set({ variables, isLoading: false });
    } catch (e: any) {
      set({ 
        error: e.message || 'Failed to fetch variables', 
        isLoading: false 
      });
      throw e; // Re-throw so component can handle
    }
  },

  createVariable: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const created = await createVariable(data);
      set((state) => ({
        variables: [...state.variables, created],
        isLoading: false,
      }));
    } catch (e: any) {
      set({ 
        error: e.message || 'Failed to create variable', 
        isLoading: false 
      });
      throw e; // Re-throw so component can handle
    }
  },

  getVariable: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const variable = await getVariable(id);
      set((state) => ({
        variables: state.variables.map(
          (v) => (v.id === id ? { ...v, ...variable } : v)
        ),
        isLoading: false,
      }));
    } catch (e: any) {
      set({ 
        error: e.message || 'Failed to get variable', 
        isLoading: false 
      });
      throw e;
    }
  },

  removeVariable: async (id) => {
    set({ isLoading: true, error: null });
    try {
      await removeVariable(id);
      set((state) => ({
        variables: state.variables.filter((v) => v.id !== id),
        isLoading: false,
      }));
    } catch (e: any) {
      set({ 
        error: e.message || 'Failed to remove variable', 
        isLoading: false 
      });
      throw e;
    }
  },

  updateVariable: async (id, inputs) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await updateVariable(id, inputs);
      set((state) => ({
        variables: state.variables.map((v) => 
          v.id === updated.id ? updated : v
        ),
        isLoading: false,
      }));
    } catch (e: any) {
      set({ 
        error: e.message || 'Failed to update variable', 
        isLoading: false 
      });
      throw e;
    }
  }
}));
