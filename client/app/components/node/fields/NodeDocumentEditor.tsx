import { useField } from "formik";
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { RefreshCw, Trash2, Plus, AlertCircle, X } from "lucide-react";
import type { NodeProperty } from "../types";
import { apiClient } from "~/lib/api-client";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";
import { VariableAutocompleteControl } from "./VariableAutocompleteField";

interface NodeDocumentEditorProps {
  property: NodeProperty;
  values: Record<string, unknown>;
  nodeType?: string;
}

interface FieldInfo {
  name: string;
  widget: "text" | "number" | "checkbox" | "datetime" | "json";
  seen: number;
}

interface NodeOptionsResponse {
  options?: FieldInfo[];
}

type DocumentValue = Record<string, unknown> | string;

const isValidFieldName = (name: string): boolean =>
  /^(?!\$)[^.\0]+(?:\.(?!\$)[^.\0]+)*$/.test(name);

const asInputValue = (value: unknown): string | number =>
  typeof value === "string" || typeof value === "number" ? value : "";

/**
 * Builds a document one field at a time.
 *
 * A collection has no declared shape, so the field names come from a sample of
 * the documents already stored and the widget for each one is chosen from the
 * values found there. That covers the fields a collection habitually carries.
 *
 * A document may also carry a field none of the others do, which is the whole
 * point of a document store, so a name and a value can be added by hand. The
 * new field then behaves like any other.
 *
 * The value is stored as a plain object keyed by field name, which is what the
 * driver expects.
 */
export const NodeDocumentEditor = ({ property, values, nodeType }: NodeDocumentEditorProps) => {
  const [field, , helpers] = useField<DocumentValue>(property.name);
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [customFields, setCustomFields] = useState<FieldInfo[]>([]);
  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldWidget, setNewFieldWidget] = useState<FieldInfo["widget"] | "">("");
  const [addingField, setAddingField] = useState(false);
  const [newFieldValue, setNewFieldValue] = useState<unknown>("");
  const requestIdRef = useRef(0);

  const dependsOn: string[] = property.optionsDependsOn || [];
  const dependencyValues = dependsOn.map((name) => values[name]);
  const dependencySignature = JSON.stringify(dependencyValues);
  const optionValues = useMemo(
    () =>
      Object.fromEntries(
        dependsOn.map((name, index) => [name, dependencyValues[index]]),
      ),
    // dependencySignature represents the selected credential/collection values.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dependsOn, dependencySignature],
  );
  const missingDependency = dependsOn.find((name) => !values[name]);

  const currentData: Record<string, unknown> = (() => {
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

  const fetchFields = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    if (!nodeType || !property.optionsMethod || missingDependency) {
      setFields([]);
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post<NodeOptionsResponse>(`/nodes/${nodeType}/options`, {
        property_name: property.name,
        values: optionValues,
      });
      if (requestId === requestIdRef.current) {
        setFields(response?.options ?? []);
      }
    } catch (err: unknown) {
      if (requestId === requestIdRef.current) {
        setError(err instanceof Error ? err.message : "Could not load the fields");
        setFields([]);
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [missingDependency, nodeType, optionValues, property.name, property.optionsMethod]);

  const previousDependencies = useRef<string | null>(null);

  useEffect(() => {
    const signature = dependencySignature;

    // The fields belonged to the collection that was chosen before, so what was
    // filled in for them has no meaning in another one. Everything is cleared,
    // including the fields added by hand. The first run is skipped, or a saved
    // document would be wiped on opening.
    if (previousDependencies.current !== null && previousDependencies.current !== signature) {
      helpers.setValue({});
      setFields([]);
      setCustomFields([]);
      setRemoved(new Set());
      setAddingField(false);
      setNewFieldName("");
      setNewFieldWidget("");
      setNewFieldValue("");
    }
    previousDependencies.current = signature;

    const requestTimer = window.setTimeout(() => {
      void fetchFields();
    }, 0);
    return () => {
      window.clearTimeout(requestTimer);
      requestIdRef.current += 1;
    };
  }, [dependencySignature, fetchFields, helpers]);

  const setFieldValue = (name: string, value: unknown) => {
    helpers.setValue({ ...currentData, [name]: value });
  };

  const dropField = (name: string) => {
    const next = { ...currentData };
    delete next[name];
    helpers.setValue(next);

    if (customFields.some((entry) => entry.name === name)) {
      setCustomFields((prev) => prev.filter((entry) => entry.name !== name));
    } else {
      setRemoved((prev) => new Set(prev).add(name));
    }
  };

  const restoreField = (name: string) => {
    setRemoved((prev) => {
      const next = new Set(prev);
      next.delete(name);
      return next;
    });
  };

  const closeAddField = () => {
    setAddingField(false);
    setNewFieldName("");
    setNewFieldWidget("");
    setNewFieldValue("");
  };

  const addCustomField = () => {
    const name = newFieldName.trim();
    if (!isValidFieldName(name) || !newFieldWidget) return;

    // A name already on the list is brought back rather than added twice.
    if (removed.has(name)) {
      restoreField(name);
    } else if (
      !customFields.some((entry) => entry.name === name) &&
      !fields.some((entry) => entry.name === name)
    ) {
      setCustomFields((prev) => [
        ...prev,
        { name, widget: newFieldWidget as FieldInfo["widget"], seen: 0 },
      ]);
    }

    setFieldValue(name, newFieldValue);
    closeAddField();
  };

  const inputClass = "kai-node-field-control min-h-0 px-3 py-2";

  /**
   * Draw the input a value of this kind is entered through.
   *
   * Kept apart from the field it belongs to so the same widget can be used both
   * for a field already on the list and for one being added, where there is no
   * field to key off yet.
   */
  const renderWidget = (
    widget: FieldInfo["widget"],
    value: unknown,
    onChange: (next: unknown) => void
  ) => {
    switch (widget) {
      case "checkbox":
        return (
          <button
            type="button"
            onClick={() => onChange(!value)}
            onMouseDown={(event) => event.stopPropagation()}
            className={`kai-node-toggle ${value ? "is-active" : ""}`}
            role="switch"
            aria-checked={Boolean(value)}
          >
            <span
              className="kai-node-toggle-thumb"
            />
          </button>
        );

      case "number":
        return (
          <input
            type="number"
            className={inputClass}
            value={asInputValue(value)}
            placeholder="Leave empty to skip this field"
            onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
            onMouseDown={(event) => event.stopPropagation()}
          />
        );

      case "datetime":
        return (
          <input
            type="datetime-local"
            className={inputClass}
            value={asInputValue(value)}
            onChange={(e) => onChange(e.target.value)}
            onMouseDown={(event) => event.stopPropagation()}
          />
        );

      case "json":
        return (
          <VariableAutocompleteControl
            name={property.name}
            as="textarea"
            rows={3}
            className={`${inputClass} font-mono text-xs`}
            value={
              typeof value === "string" ? value : value ? JSON.stringify(value, null, 2) : ""
            }
            placeholder=' JSON list or object'
            onValueChange={onChange}
            onMouseDown={(event) => event.stopPropagation()}
          />
        );

      default:
        return (
          <VariableAutocompleteControl
            name={property.name}
            className={inputClass}
            value={String(asInputValue(value))}
            placeholder="Leave empty to skip this field"
            onValueChange={onChange}
            onMouseDown={(event) => event.stopPropagation()}
          />
        );
    }
  };

  const renderInput = (name: string, widget: FieldInfo["widget"]) =>
    renderWidget(widget, currentData[name], (next) => setFieldValue(name, next));

  const discovered = fields.filter((entry) => !removed.has(entry.name));
  const dropped = fields.filter((entry) => removed.has(entry.name));

  const renderRow = (name: string, widget: FieldInfo["widget"], note?: string) => (
    <div key={name} className="border-l-2 border-[var(--kai-border-strong)] pl-3">
      <div className="flex items-center gap-2 mb-1.5">
        <button
          type="button"
          title="Leave this field out"
          onClick={() => dropField(name)}
          className="text-[var(--kai-text-muted)] transition-colors hover:text-[var(--kai-danger-text-soft)]"
        >
          <Trash2 size={13} />
        </button>
        <span className="text-sm text-[var(--kai-text-soft)]">{name}</span>
        {note && <span className="text-xs text-[var(--kai-accent-text)]">{note}</span>}
        <span className="ml-auto text-xs text-[var(--kai-text-muted)]">{widget}</span>
      </div>
      {renderInput(name, widget)}
    </div>
  );

  return (
    <div className={`${property?.colSpan ? `col-span-${property?.colSpan}` : "col-span-2"}`}>
      <div className="flex items-center justify-between">
        <FieldLabel label={property.displayName} helpText={getFieldHelpText(property)} />
        <button
          type="button"
          title="Reload the fields"
          onClick={fetchFields}
          disabled={loading || !!missingDependency}
          className="p-1 text-[var(--kai-text-muted)] transition-colors hover:text-[var(--kai-accent-text)] disabled:cursor-not-allowed disabled:text-[var(--kai-text-disabled)]"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {missingDependency && (
        <div className="py-3 text-sm text-[var(--kai-text-muted)]">
          Select {missingDependency.replace(/_/g, " ")} first.
        </div>
      )}

      {loading && <div className="py-3 text-sm text-[var(--kai-text-muted)]">Loading the fields...</div>}

      {error && (
        <div className="flex items-start gap-1.5 py-2 text-xs text-[var(--kai-warning)]">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !missingDependency && !error && fields.length === 0 && (
        <div className="py-3 text-sm text-[var(--kai-text-muted)]">
          The collection is empty, so there are no field names to suggest. Add them below.
        </div>
      )}

      <div className="space-y-3 mt-1">
        {discovered.map((entry) => renderRow(entry.name, entry.widget))}
        {customFields.map((entry) => renderRow(entry.name, entry.widget, "(new field)"))}
      </div>

      {!missingDependency && !addingField && (
        <button
          type="button"
          onClick={() => setAddingField(true)}
          onMouseDown={(event) => event.stopPropagation()}
          className="mt-3 flex items-center gap-1.5 rounded-lg border border-dashed border-[var(--kai-config-dashed-border)] px-3 py-2 text-sm text-[var(--kai-text-muted)] transition-colors hover:border-[var(--kai-accent)] hover:text-[var(--kai-accent-text)]"
        >
          <Plus size={14} />
          Add field
        </button>
      )}

      {!missingDependency && addingField && (
        <div className="mt-3 rounded-lg border border-[var(--kai-border-strong)] bg-[var(--kai-surface-control)]/40 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[var(--kai-text-secondary)]">New field</span>
            <button
              type="button"
              title="Cancel"
              onClick={closeAddField}
              onMouseDown={(event) => event.stopPropagation()}
              className="text-[var(--kai-text-muted)] transition-colors hover:text-[var(--kai-danger-text-soft)]"
            >
              <X size={14} />
            </button>
          </div>

          <div className="space-y-2">
            <div>
              <div className="mb-1 text-xs text-[var(--kai-text-muted)]">Field name</div>
              <input
                type="text"
                autoFocus
                className={inputClass}
                value={newFieldName}
                placeholder="Name of the field"
                onChange={(e) => setNewFieldName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") closeAddField();
                }}
                onMouseDown={(event) => event.stopPropagation()}
              />
            </div>

            <div>
              <div className="mb-1 text-xs text-[var(--kai-text-muted)]">Value type</div>
              <select
                className={`${inputClass} ${newFieldWidget ? "" : "text-[var(--kai-placeholder)]"}`}
                value={newFieldWidget}
                onChange={(e) => {
                  const kind = e.target.value as FieldInfo["widget"];
                  setNewFieldWidget(kind);
                  // The value starts over, since what was typed for one kind
                  // rarely fits another.
                  setNewFieldValue(kind === "checkbox" ? false : "");
                }}
                onMouseDown={(event) => event.stopPropagation()}
              >
                <option value="">Select a type</option>
                <option value="text">Text</option>
                <option value="number">Number</option>
                <option value="checkbox">True or false</option>
                <option value="datetime">Date</option>
                <option value="json">List or object</option>
              </select>
            </div>

            {newFieldWidget && (
              <div>
                <div className="mb-1 text-xs text-[var(--kai-text-muted)]">Value</div>
                {renderWidget(
                  newFieldWidget as FieldInfo["widget"],
                  newFieldValue,
                  (next) => setNewFieldValue(next),
                )}
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={addCustomField}
                disabled={!isValidFieldName(newFieldName.trim()) || !newFieldWidget}
                onMouseDown={(event) => event.stopPropagation()}
                className={`px-4 py-2 rounded-lg border transition-colors text-sm ${
                  isValidFieldName(newFieldName.trim()) && newFieldWidget
                    ? "border-[var(--kai-accent)] text-[var(--kai-accent-text)] hover:bg-[var(--kai-accent-subtle)]"
                    : "cursor-not-allowed border-[var(--kai-border-strong)] text-[var(--kai-text-disabled)]"
                }`}
              >
                Add
              </button>
              <button
                type="button"
                onClick={closeAddField}
                onMouseDown={(event) => event.stopPropagation()}
                className="kai-node-field-action px-4 py-2 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>

          <div className="mt-2 text-xs text-[var(--kai-text-muted)]">
            The kind decides how the value is stored, so a number stays a number and a code
            keeps its leading zero.
          </div>
        </div>
      )}

      {dropped.length > 0 && (
        <div className="mt-3 border-t border-[var(--kai-border-strong)] pt-3">
          <div className="mb-2 text-xs text-[var(--kai-text-muted)]">Fields left out</div>
          <div className="flex flex-wrap gap-2">
            {dropped.map((entry) => (
              <button
                key={entry.name}
                type="button"
                onClick={() => restoreField(entry.name)}
                className="kai-node-field-action flex items-center gap-1 rounded px-2 py-1 text-xs"
              >
                <Plus size={11} />
                {entry.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {!missingDependency && fields.length > 0 && (
        <div className="mt-2 text-xs text-[var(--kai-text-muted)]">
          Fields left empty are not written.
        </div>
      )}
    </div>
  );
};

export default NodeDocumentEditor;
