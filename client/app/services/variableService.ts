import { apiClient } from '../lib/api-client';
import { API_ENDPOINTS } from '../lib/config';
import type { Variable, VariableCreateRequest } from '../types/api';

export const createVariable = async (inputs: VariableCreateRequest) => {
  return apiClient.post<Variable>(API_ENDPOINTS.VARIABLES.CREATE, inputs);
};

export const getVariable = async (variable_id: string) => {
  return apiClient.get<Variable>(API_ENDPOINTS.VARIABLES.GET(variable_id));
};

export const listVariables = async (params?: { skip?: number; limit?: number }) => {
  return apiClient.get<Variable[]>(API_ENDPOINTS.VARIABLES.LIST, { params });
}; 

export const removeVariable = async(variable_id:string)=>{
    return apiClient.delete(API_ENDPOINTS.VARIABLES.DELETE(variable_id));
}
export const updateVariable = async(variable_id:string,inputs:Partial<VariableCreateRequest>)=>{
    return apiClient.put<Variable>(API_ENDPOINTS.VARIABLES.UPDATE(variable_id),inputs);
}
