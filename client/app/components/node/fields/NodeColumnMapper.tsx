import { useField } from "formik";
import { useState, useEffect, useCallback } from "react";
import { RefreshCw, Trash2, Plus, AlertCircle } from "lucide-react";
import type { NodeProperty } from "../types";
import { apiClient } from "~/lib/api-client";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

interface NodeColumnMapperProps {
  property: NodeProperty;
  values: any;
  nodeType?: string;
}

interface ColumnInfo {
  name: string;
  type: string;
  widget: "text" | "number" | "checkbox" | "datetime" | "json";
  required: boolean;
  hasDefault: boolean;
}

/**
 * Renders one input per column of the selected table.
 *
 * The column list and each column's data type come from the backend, so the
 * panel shows a checkbox for a boolean column, a date picker for a timestamp
 * and so on. The value is stored as a single object keyed by column name.
 *
 * Columns named as match columns are marked and cannot be removed, since their
 * value is what identifies the row.
 */
export const NodeColumnMapper = ({ property, values, nodeType }: NodeColumnMapperProps) => {
  const [field, , helpers] = useField(property.name);
  const [columns, setColumns] = useState<ColumnInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [removed, setRemoved] = useState<Set<string>>(new Set());

  const dependsOn: string[] = property.optionsDependsOn || [];
  const dependencyValues = dependsOn.map((name) => values[name]);
  const missingDependency = dependsOn.find((name) => !values[name]);

  // Match columns are read from the sibling field so they can be marked.
  const matchColumns: string[] = (() => {
    const raw = values.match_columns;
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.map(String);
    return String(raw)
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
  })();

  const currentData: Record<string, any> = (() => {
    const raw = field.value;
    if (!raw) return {};
    if (typeof raw === "object" && !Array.isArray(raw)) return raw;
    if (typeof raw === "string") {
      try {
        const parsed = JSON.parse(raw);
        return typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
      } catch {
        return {};
      }
    }
    return {};
  })();

  const fetchColumns = useCallback(async () => {
    if (!nodeType || !property.optionsMethod || missingDependency) {
      setColumns([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // The shared client carries the base URL, the auth header and refresh
      // handling, so the request behaves like every other call in the app.
      const response = await apiClient.post(`/nodes/${nodeType}/options`, {
        property_name: property.name,
        values,
      });

      setColumns(response?.options ?? []);
    } catch (err: any) {
      setError(err?.message ?? "Could not load the columns");
      setColumns([]);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeType, property.name, ...dependencyValues]);

  useEffect(() => {
    fetchColumns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencyValues]);

  const setColumnValue = (name: string, value: any) => {
    helpers.setValue({ ...currentData, [name]: value });
  };

  const removeColumn = (name: string) => {
    const next = { ...currentData };
    delete next[name];
    helpers.setValue(next);
    setRemoved((prev) => new Set(prev).add(name));
  };

  const restoreColumn = (name: string) => {
    setRemoved((prev) => {
      const next = new Set(prev);
      next.delete(name);
      return next;
    });
  };

  const inputClass =
    "w-full bg-[#10182c] border border-slate-600 rounded-lg px-3 py-2 text-sm text-white " +
    "placeholder:text-slate-500 focus:border-blue-500 focus:outline-none transition-colors";

  const renderInput = (column: ColumnInfo) => {
    const value = currentData[column.name];

    switch (column.widget) {
      case "checkbox":
        return (
          <button
            type="button"
            onClick={() => setColumnValue(column.name, !value)}
            className={`relative w-11 h-6 rounded-full transition-colors ${
              value ? "bg-blue-500" : "bg-slate-600"
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                value ? "translate-x-5" : ""
              }`}
            />
          </button>
        );

      case "number":
        return (
          <input
            type="number"
            className={inputClass}
            value={value ?? ""}
            placeholder={column.hasDefault ? "Leave empty to use the default" : ""}
            onChange={(e) =>
              setColumnValue(column.name, e.target.value === "" ? null : Number(e.target.value))
            }
          />
        );

      case "datetime":
        return (
          <input
            type="datetime-local"
            className={inputClass}
            value={value ?? ""}
            onChange={(e) => setColumnValue(column.name, e.target.value || null)}
          />
        );

      case "json":
        return (
          <textarea
            rows={3}
            className={`${inputClass} font-mono text-xs`}
            value={typeof value === "string" ? value : value ? JSON.stringify(value, null, 2) : ""}
            placeholder="{}"
            onChange={(e) => setColumnValue(column.name, e.target.value)}
          />
        );

      default:
        return (
          <input
            type="text"
            className={inputClass}
            value={value ?? ""}
            placeholder={column.hasDefault ? "Leave empty to use the default" : ""}
            onChange={(e) => setColumnValue(column.name, e.target.value)}
          />
        );
    }
  };

  const visibleColumns = columns.filter((column) => !removed.has(column.name));
  const removedColumns = columns.filter((column) => removed.has(column.name));

  return (
    <div className={`${property?.colSpan ? `col-span-${property?.colSpan}` : "col-span-2"}`}>
      <div className="flex items-center justify-between">
        <FieldLabel label={property.displayName} helpText={getFieldHelpText(property)} />
        <button
          type="button"
          title="Reload the columns"
          onClick={fetchColumns}
          disabled={loading || !!missingDependency}
          className="text-slate-400 hover:text-blue-300 disabled:text-slate-600 disabled:cursor-not-allowed p-1"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {missingDependency && (
        <div className="text-sm text-slate-400 py-3">
          Select {missingDependency.replace(/_/g, " ")} first.
        </div>
      )}

      {loading && <div className="text-sm text-slate-400 py-3">Loading the columns...</div>}

      {error && (
        <div className="flex items-start gap-1.5 py-2 text-xs text-amber-400">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !missingDependency && !error && columns.length === 0 && (
        <div className="text-sm text-slate-400 py-3">This table has no columns to show.</div>
      )}

      <div className="space-y-3 mt-1">
        {visibleColumns.map((column) => {
          const isMatch = matchColumns.includes(column.name);
          return (
            <div key={column.name} className="pl-3 border-l-2 border-slate-700">
              <div className="flex items-center gap-2 mb-1.5">
                {!isMatch && (
                  <button
                    type="button"
                    title="Leave this column out"
                    onClick={() => removeColumn(column.name)}
                    className="text-slate-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
                <span className="text-sm text-slate-200">{column.name}</span>
                {isMatch && (
                  <span className="text-xs text-blue-300">(using to match)</span>
                )}
                {column.required && !isMatch && (
                  <span className="text-xs text-amber-400">required</span>
                )}
                <span className="text-xs text-slate-500 ml-auto">{column.type}</span>
              </div>
              {renderInput(column)}
            </div>
          );
        })}
      </div>

      {removedColumns.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-700">
          <div className="text-xs text-slate-500 mb-2">Columns left out</div>
          <div className="flex flex-wrap gap-2">
            {removedColumns.map((column) => (
              <button
                key={column.name}
                type="button"
                onClick={() => restoreColumn(column.name)}
                className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 border border-slate-700 rounded hover:text-blue-300 hover:border-blue-500 transition-colors"
              >
                <Plus size={11} />
                {column.name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default NodeColumnMapper;