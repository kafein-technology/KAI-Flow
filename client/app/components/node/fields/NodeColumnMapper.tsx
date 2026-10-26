import { useField } from "formik";
import { useState, useEffect, useCallback, useRef } from "react";
import { RefreshCw, Trash2, Plus, AlertCircle, RotateCcw } from "lucide-react";
import type { NodeProperty } from "../types";
import { apiClient } from "~/lib/api-client";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";
import { ThemedDateTimeInput } from "./ThemedDateTimeInput";
import { ThemedNumberInput } from "./ThemedNumberInput";
import { VariableAutocompleteControl } from "./VariableAutocompleteField";

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

  const inputClass = "kai-node-field-control min-h-0 px-3 py-2";

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
          <VariableAutocompleteControl
            name={column.name}
            as="textarea"
            rows={3}
            className={`${inputClass} font-mono text-xs`}
            value={typeof value === "string" ? value : value ? JSON.stringify(value, null, 2) : ""}
            placeholder={column.required ? "Required JSON value" : "{}"}
            onValueChange={(next) => setColumnValue(column.name, next)}
          />
        );

      default:
        return (
          <VariableAutocompleteControl
            name={column.name}
            className={inputClass}
            value={String(value ?? "")}
            placeholder={placeholderFor(column)}
            onValueChange={(next) => setColumnValue(column.name, next)}
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
              className="p-1 text-[var(--kai-text-muted)] transition-colors hover:text-[var(--kai-warning)]"
            >
              <RotateCcw size={14} />
            </button>
          )}
          <button
            type="button"
            title="Reload the columns"
            onClick={fetchColumns}
            disabled={loading || !!missingDependency}
            className="p-1 text-[var(--kai-text-muted)] transition-colors hover:text-[var(--kai-accent-text)] disabled:cursor-not-allowed disabled:text-[var(--kai-text-disabled)]"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {!missingDependency && columns.length > 0 && (
        <div className="mb-3 rounded-md border border-[var(--kai-accent-soft)] bg-[var(--kai-accent-subtle)] px-3 py-2 text-xs text-[var(--kai-text-muted)]">
          {operation === "update"
            ? "Only included columns are updated. An included empty value overwrites the existing value; remove the column to leave it unchanged."
            : "Only included columns are sent. Remove optional/defaulted columns when PostgreSQL should supply their value."}
        </div>
      )}

      {missingDependency && (
        <div className="py-3 text-sm text-[var(--kai-text-muted)]">
          Select {missingDependency.replace(/_/g, " ")} first.
        </div>
      )}

      {loading && <div className="py-3 text-sm text-[var(--kai-text-muted)]">Loading the columns...</div>}

      {error && (
        <div className="flex items-start gap-1.5 py-2 text-xs text-[var(--kai-warning)]">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !missingDependency && !error && columns.length === 0 && (
        <div className="py-3 text-sm text-[var(--kai-text-muted)]">This table has no columns to show.</div>
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
            <div key={column.name} className="border-l-2 border-[var(--kai-accent-strong)] pl-3">
              <div className="flex items-center gap-2 mb-1.5">
                {!isMatch && !isLockedRequired && (
                  <button
                    type="button"
                    title="Do not send this column"
                    onClick={() => removeColumn(column.name)}
                    className="text-[var(--kai-text-muted)] transition-colors hover:text-[var(--kai-danger-text-soft)]"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
                <span className="text-sm text-[var(--kai-text-soft)]">{column.name}</span>
                {isMatch && (
                  <span className="text-xs text-[var(--kai-accent-text)]">(using to match)</span>
                )}
                {column.required && isInsertLike && !isMatch && (
                  <span className="text-xs text-[var(--kai-warning)]">required</span>
                )}
                {isExplicitlyMapped ? (
                  <span className="text-[10px] uppercase tracking-wide text-[var(--kai-success-text)]">
                    included
                  </span>
                ) : (
                  <span className="text-[10px] uppercase tracking-wide text-[var(--kai-warning)]">
                    value required
                  </span>
                )}
                <span className="ml-auto text-xs text-[var(--kai-text-muted)]">{column.type}</span>
              </div>
              {renderInput(column)}
              {sendsBlankValue && (
                <div className="mt-1 text-xs text-[var(--kai-warning)]">
                  This empty value will be sent. Remove the column to leave it unchanged.
                </div>
              )}
            </div>
          );
        })}
      </div>

      {availableColumns.length > 0 && (
        <div className="mt-3 border-t border-[var(--kai-border-strong)] pt-3">
          <div className="mb-2 text-xs text-[var(--kai-text-muted)]">
            Available columns — not sent until included
          </div>
          <div className="flex flex-wrap gap-2">
            {availableColumns.map((column) => (
              <button
                key={column.name}
                type="button"
                onClick={() => includeColumn(column.name)}
                className="kai-node-field-action flex items-center gap-1 rounded px-2 py-1 text-xs"
              >
                <Plus size={11} />
                {column.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <details className="mt-3 border-t border-[var(--kai-border-strong)] pt-3">
        <summary className="cursor-pointer text-xs text-[var(--kai-text-muted)] transition-colors hover:text-[var(--kai-text)]">
          Payload preview ({Object.keys(currentData).length} mapped column
          {Object.keys(currentData).length === 1 ? "" : "s"})
        </summary>
        <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-[var(--kai-bg-deep)] p-3 text-xs text-[var(--kai-text-secondary)]">
          {JSON.stringify(currentData, null, 2)}
        </pre>
      </details>
    </div>
  );
};

export default NodeColumnMapper;
