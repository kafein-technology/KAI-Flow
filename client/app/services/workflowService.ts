// Workflow Service Template
import axios from 'axios';
import { apiClient } from '../lib/api-client';
import { API_ENDPOINTS, config } from '../lib/config';

const API_BASE_URL = `/${config.API_START}/workflow`;

export const getWorkflows = async () => {
  return axios.get(API_BASE_URL);
};

export const getWorkflowById = async (id: string | number) => {
  return axios.get(`${API_BASE_URL}/${id}`);
};

export const createWorkflow = async (data: any) => {
  return axios.post(API_BASE_URL, data);
};

export const updateWorkflow = async (id: string | number, data: any) => {
  return axios.put(`${API_BASE_URL}/${id}`, data);
};

export const deleteWorkflow = async (id: string | number) => {
  return axios.delete(`${API_BASE_URL}/${id}`);
};

import { broadcastExecutionStarted } from './executionService';

export const executeWorkflow = async (
  flow_data: any,
  input_text: string,
  chatflow_id?: string,
  session_id?: string,
  workflow_id?: string
) => {
  const response = await apiClient.post(API_ENDPOINTS.WORKFLOWS.EXECUTE, {
    flow_data,
    input_text,
    chatflow_id,
    session_id,
    workflow_id,
  });
  broadcastExecutionStarted();
  return response;
}; 