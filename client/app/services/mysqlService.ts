import { apiClient } from "~/lib/api-client";
import { API_ENDPOINTS } from "~/lib/config";

export interface MySQLSchemaInfo {
  name: string;
}

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

export const getMySQLSchemas = (credentialId: string) =>
  apiClient.get<MySQLSchemaInfo[]>(API_ENDPOINTS.MYSQL.SCHEMAS, {
    params: { credential_id: credentialId },
  });

export const getMySQLTables = (credentialId: string, schema = "", search = "") =>
  apiClient.get<MySQLTableInfo[]>(API_ENDPOINTS.MYSQL.TABLES, {
    params: { credential_id: credentialId, schema, search },
  });

export const getMySQLColumns = (credentialId: string, table: string, schema = "") =>
  apiClient.get<MySQLColumnInfo[]>(API_ENDPOINTS.MYSQL.COLUMNS, {
    params: { credential_id: credentialId, table, schema },
  });
