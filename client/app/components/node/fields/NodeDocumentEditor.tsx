import { useField } from "formik";
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { RefreshCw, Trash2, Plus, AlertCircle, X } from "lucide-react";
import type { NodeProperty } from "../types";
import { apiClient } from "~/lib/api-client";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

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

  const inputClass =
    "w-full bg-[#10182c] border border-slate-600 rounded-lg px-3 py-2 text-sm text-white " +
    "placeholder:text-slate-500 focus:border-blue-500 focus:outline-none transition-colors";

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
          <textarea
            rows={3}
            className={`${inputClass} font-mono text-xs`}
            value={
              typeof value === "string" ? value : value ? JSON.stringify(value, null, 2) : ""
            }
            placeholder=' JSON list or object'
            onChange={(e) => onChange(e.target.value)}
            onMouseDown={(event) => event.stopPropagation()}
          />
        );

      default:
        return (
          <input
            type="text"
            className={inputClass}
            value={asInputValue(value)}
            placeholder="Leave empty to skip this field"
            onChange={(e) => onChange(e.target.value)}
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
    <div key={name} className="pl-3 border-l-2 border-slate-700">
      <div className="flex items-center gap-2 mb-1.5">
        <button
          type="button"
          title="Leave this field out"
          onClick={() => dropField(name)}
          className="text-slate-500 hover:text-red-400 transition-colors"
        >
          <Trash2 size={13} />
        </button>
        <span className="text-sm text-slate-200">{name}</span>
        {note && <span className="text-xs text-blue-300">{note}</span>}
        <span className="text-xs text-slate-500 ml-auto">{widget}</span>
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

      {loading && <div className="text-sm text-slate-400 py-3">Loading the fields...</div>}

      {error && (
        <div className="flex items-start gap-1.5 py-2 text-xs text-amber-400">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !missingDependency && !error && fields.length === 0 && (
        <div className="text-sm text-slate-400 py-3">
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
          className="flex items-center gap-1.5 mt-3 px-3 py-2 text-sm rounded-lg border border-dashed border-slate-600 text-slate-400 hover:text-blue-300 hover:border-blue-500 transition-colors"
        >
          <Plus size={14} />
          Add field
        </button>
      )}

      {!missingDependency && addingField && (
        <div className="mt-3 p-3 rounded-lg border border-slate-700 bg-slate-800/40">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-slate-300">New field</span>
            <button
              type="button"
              title="Cancel"
              onClick={closeAddField}
              onMouseDown={(event) => event.stopPropagation()}
              className="text-slate-500 hover:text-red-400 transition-colors"
            >
              <X size={14} />
            </button>
          </div>

          <div className="space-y-2">
            <div>
              <div className="text-xs text-slate-400 mb-1">Field name</div>
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
              <div className="text-xs text-slate-400 mb-1">Value type</div>
              <select
                className={`${inputClass} ${newFieldWidget ? "" : "text-slate-500"}`}
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
                <div className="text-xs text-slate-400 mb-1">Value</div>
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
                    ? "border-blue-500 text-blue-300 hover:bg-blue-500/20"
                    : "border-slate-700 text-slate-600 cursor-not-allowed"
                }`}
              >
                Add
              </button>
              <button
                type="button"
                onClick={closeAddField}
                onMouseDown={(event) => event.stopPropagation()}
                className="px-4 py-2 rounded-lg border border-slate-700 text-slate-400 hover:text-slate-200 transition-colors text-sm"
              >
                Cancel
              </button>
            </div>
          </div>

          <div className="text-xs text-slate-500 mt-2">
            The kind decides how the value is stored, so a number stays a number and a code
            keeps its leading zero.
          </div>
        </div>
      )}

      {dropped.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-700">
          <div className="text-xs text-slate-500 mb-2">Fields left out</div>
          <div className="flex flex-wrap gap-2">
            {dropped.map((entry) => (
              <button
                key={entry.name}
                type="button"
                onClick={() => restoreField(entry.name)}
                className="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 border border-slate-700 rounded hover:text-blue-300 hover:border-blue-500 transition-colors"
              >
                <Plus size={11} />
                {entry.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {!missingDependency && fields.length > 0 && (
        <div className="text-xs text-slate-500 mt-2">
          Fields left empty are not written.
        </div>
      )}
    </div>
  );
};

export default NodeDocumentEditor;
