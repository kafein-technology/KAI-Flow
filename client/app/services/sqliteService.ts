import { apiClient } from "~/lib/api-client";
import { API_ENDPOINTS } from "~/lib/config";

export interface SQLiteTableInfo {
  name: string;
  type: string;
}

export interface SQLiteColumnInfo {
  name: string;
  data_type: string;
  column_type: string;
  nullable: boolean;
  default: unknown;
  key: string;
  extra: string;
}

export const getSQLiteTables = (credentialId: string, search = "") =>
  apiClient.get<SQLiteTableInfo[]>(API_ENDPOINTS.SQLITE.TABLES, {
    params: { credential_id: credentialId, search },
  });

export const getSQLiteColumns = (credentialId: string, table: string) =>
  apiClient.get<SQLiteColumnInfo[]>(API_ENDPOINTS.SQLITE.COLUMNS, {
    params: { credential_id: credentialId, table },
  });
