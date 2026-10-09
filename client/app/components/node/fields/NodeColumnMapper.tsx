import { useField } from "formik";
import { useState, useEffect, useCallback, useRef } from "react";
import { RefreshCw, Trash2, Plus, AlertCircle, RotateCcw } from "lucide-react";
import type { NodeProperty } from "../types";
import { apiClient } from "~/lib/api-client";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";
import { ThemedDateTimeInput } from "./ThemedDateTimeInput";
import { ThemedNumberInput } from "./ThemedNumberInput";

interface NodeColumnMapperProps {
  property: NodeProperty;
  values: any;
  nodeType?: string;
  sessionStore?: Record<
    string,
    {
      currentKey: string;
      valuesByContext: Record<string, any>;
    }
  >;
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
export const NodeColumnMapper = ({
  property,
  values,
  nodeType,
  sessionStore,
}: NodeColumnMapperProps) => {
  const [field, , helpers] = useField(property.name);
  const [columns, setColumns] = useState<ColumnInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const latestValuesRef = useRef(values);
  latestValuesRef.current = values;

  const dependsOn: string[] = property.optionsDependsOn || [];
  const dependencyValues = dependsOn.map((name) => values[name]);
  const dependencyKey = JSON.stringify(dependencyValues);
  const missingDependency = dependsOn.find((name) => !values[name]);
  const operation = String(values.operation || "").toLowerCase();
  const contextKey = JSON.stringify({ operation, dependencyValues });
  const isInsertLike = operation === "insert" || operation === "upsert";

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

  // Keep mapper values isolated by operation and database target for the
  // lifetime of the open form. Switching Insert -> Update starts with a clean
  // update payload; switching back restores the Insert draft.
  useEffect(() => {
    if (!sessionStore) return;

    const existing = sessionStore[property.name];
    if (!existing) {
      sessionStore[property.name] = {
        currentKey: contextKey,
        valuesByContext: { [contextKey]: field.value ?? {} },
      };
      return;
    }

    if (existing.currentKey !== contextKey) {
      existing.valuesByContext[existing.currentKey] = field.value ?? {};
      const nextValue = existing.valuesByContext[contextKey] ?? {};
      existing.currentKey = contextKey;
      existing.valuesByContext[contextKey] = nextValue;
      helpers.setValue(nextValue);
      return;
    }

    existing.valuesByContext[contextKey] = field.value ?? {};
  }, [contextKey, field.value, helpers, property.name, sessionStore]);

  const fetchColumns = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    if (!nodeType || !property.optionsMethod || missingDependency) {
      setColumns([]);
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // The shared client carries the base URL, the auth header and refresh
      // handling, so the request behaves like every other call in the app.
      const response = await apiClient.post(`/nodes/${nodeType}/options`, {
        property_name: property.name,
        values: latestValuesRef.current,
      });

      if (requestId === requestIdRef.current) {
        setColumns(response?.options ?? []);
      }
    } catch (err: any) {
      if (requestId === requestIdRef.current) {
        setError(err?.message ?? "Could not load the columns");
        setColumns([]);
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [dependencyKey, missingDependency, nodeType, property.name, property.optionsMethod]);

  useEffect(() => {
    fetchColumns();
  }, [fetchColumns]);

  const setColumnValue = (name: string, value: any) => {
    helpers.setValue({ ...currentData, [name]: value });
  };

  const removeColumn = (name: string) => {
    const next = { ...currentData };
    delete next[name];
    helpers.setValue(next);
  };

  const includeColumn = (name: string) => {
    helpers.setValue({ ...currentData, [name]: "" });
  };

  const clearMappedValues = () => {
    const matchValues = Object.fromEntries(
      matchColumns
        .filter((name) => Object.prototype.hasOwnProperty.call(currentData, name))
        .map((name) => [name, currentData[name]])
    );
    helpers.setValue(matchValues);
  };

  const inputClass =
    "w-full bg-[#10182c] border border-slate-600 rounded-lg px-3 py-2 text-sm text-white " +
    "placeholder:text-slate-500 focus:border-blue-500 focus:outline-none transition-colors";

  const hasMappedValue = (name: string) =>
    Object.prototype.hasOwnProperty.call(currentData, name);

  const isColumnIncluded = (column: ColumnInfo) =>
    hasMappedValue(column.name) ||
    matchColumns.includes(column.name) ||
    (isInsertLike && column.required);

  const placeholderFor = (column: ColumnInfo) => {
    if (operation === "update") return "Empty value overwrites the current value";
    if (column.hasDefault) return "Enter a value or remove the column to use its default";
    return column.required ? "Required value" : "Enter a value";
  };

  const renderInput = (column: ColumnInfo) => {
    const value = currentData[column.name];

    switch (column.widget) {
      case "checkbox":
        return (
          <select
            className={inputClass}
            value={value === true ? "true" : value === false ? "false" : ""}
            onChange={(event) => {
              if (event.target.value === "") {
                removeColumn(column.name);
              } else {
                setColumnValue(column.name, event.target.value === "true");
              }
            }}
          >
            <option value="">Select true or false</option>
            <option value="true">True</option>
            <option value="false">False</option>
          </select>
        );

      case "number":
        return (
          <ThemedNumberInput
            value={value ?? ""}
            placeholder={placeholderFor(column)}
            ariaLabel={column.name}
            size="compact"
            onChange={(nextValue) =>
              setColumnValue(column.name, nextValue === "" ? null : Number(nextValue))
            }
          />
        );

      case "datetime":
        return (
          <ThemedDateTimeInput
            value={value}
            placeholder={placeholderFor(column)}
            onChange={(nextValue) => setColumnValue(column.name, nextValue || null)}
          />
        );

      case "json":
        return (
          <textarea
            rows={3}
            className={`${inputClass} font-mono text-xs`}
            value={typeof value === "string" ? value : value ? JSON.stringify(value, null, 2) : ""}
            placeholder={column.required ? "Required JSON value" : "{}"}
            onChange={(e) => setColumnValue(column.name, e.target.value)}
          />
        );

      default:
        return (
          <input
            type="text"
            className={inputClass}
            value={value ?? ""}
            placeholder={placeholderFor(column)}
            onChange={(e) => setColumnValue(column.name, e.target.value)}
          />
        );
    }
  };

  const includedColumns = columns.filter(isColumnIncluded);
  const availableColumns = columns.filter((column) => !isColumnIncluded(column));

  return (
    <div className={`${property?.colSpan ? `col-span-${property?.colSpan}` : "col-span-2"}`}>
      <div className="flex items-center justify-between">
        <FieldLabel label={property.displayName} helpText={getFieldHelpText(property)} />
        <div className="flex items-center gap-1">
          {Object.keys(currentData).length > 0 && (
            <button
              type="button"
              title="Clear mapped values except match columns"
              onClick={clearMappedValues}
              className="text-slate-400 hover:text-amber-300 p-1"
            >
              <RotateCcw size={14} />
            </button>
          )}
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
      </div>

      {!missingDependency && columns.length > 0 && (
        <div className="mb-3 rounded-md border border-blue-500/20 bg-blue-500/5 px-3 py-2 text-xs text-slate-400">
          {operation === "update"
            ? "Only included columns are updated. An included empty value overwrites the existing value; remove the column to leave it unchanged."
            : "Only included columns are sent. Remove optional/defaulted columns when PostgreSQL should supply their value."}
        </div>
      )}

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
        {includedColumns.map((column) => {
          const isMatch = matchColumns.includes(column.name);
          const isLockedRequired = isInsertLike && column.required;
          const isExplicitlyMapped = hasMappedValue(column.name);
          const sendsBlankValue =
            isExplicitlyMapped &&
            (currentData[column.name] === "" || currentData[column.name] === null);
          return (
            <div key={column.name} className="pl-3 border-l-2 border-blue-500/50">
              <div className="flex items-center gap-2 mb-1.5">
                {!isMatch && !isLockedRequired && (
                  <button
                    type="button"
                    title="Do not send this column"
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
                {column.required && isInsertLike && !isMatch && (
                  <span className="text-xs text-amber-400">required</span>
                )}
                {isExplicitlyMapped ? (
                  <span className="text-[10px] uppercase tracking-wide text-emerald-400">
                    included
                  </span>
                ) : (
                  <span className="text-[10px] uppercase tracking-wide text-amber-400">
                    value required
                  </span>
                )}
                <span className="text-xs text-slate-500 ml-auto">{column.type}</span>
              </div>
              {renderInput(column)}
              {sendsBlankValue && (
                <div className="mt-1 text-xs text-amber-400">
                  This empty value will be sent. Remove the column to leave it unchanged.
                </div>
              )}
            </div>
          );
        })}
      </div>

      {availableColumns.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-700">
          <div className="text-xs text-slate-500 mb-2">
            Available columns — not sent until included
          </div>
          <div className="flex flex-wrap gap-2">
            {availableColumns.map((column) => (
              <button
                key={column.name}
                type="button"
                onClick={() => includeColumn(column.name)}
                className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 border border-slate-700 rounded hover:text-blue-300 hover:border-blue-500 transition-colors"
              >
                <Plus size={11} />
                {column.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <details className="mt-3 border-t border-slate-700 pt-3">
        <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-200">
          Payload preview ({Object.keys(currentData).length} mapped column
          {Object.keys(currentData).length === 1 ? "" : "s"})
        </summary>
        <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-[#0b1220] p-3 text-xs text-slate-300">
          {JSON.stringify(currentData, null, 2)}
        </pre>
      </details>
    </div>
  );
};

export default NodeColumnMapper;
