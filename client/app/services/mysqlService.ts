import { apiClient } from "~/lib/api-client";
import { API_ENDPOINTS } from "~/lib/config";

export interface MySQLTableInfo {
  name: string;
  type: string;
}

export interface MySQLColumnInfo {
  name: string;
  data_type: string;
  column_type: string;
  nullable: boolean;
  default: unknown;
  key: string;
  extra: string;
}

export const getMySQLTables = (credentialId: string, search = "") =>
  apiClient.get<MySQLTableInfo[]>(API_ENDPOINTS.MYSQL.TABLES, {
    params: { credential_id: credentialId, search },
  });

export const getMySQLColumns = (credentialId: string, table: string) =>
  apiClient.get<MySQLColumnInfo[]>(API_ENDPOINTS.MYSQL.COLUMNS, {
    params: { credential_id: credentialId, table },
  });
