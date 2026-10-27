import { useField } from "formik";
import { useState, useRef, useEffect, useCallback } from "react";
import { ChevronDown, RefreshCw, AlertCircle, Check, X } from "lucide-react";
import type { NodeProperty } from "../types";
import { apiClient } from "~/lib/api-client";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

interface NodeDynamicSelectProps {
  property: NodeProperty;
  values: any;
  nodeType?: string;
}

interface Option {
  label: string;
  value: string;
  description?: string;
}

/**
 * A field that offers values fetched from the backend while still letting the
 * value be typed by hand.
 *
 * The node declares `optionsMethod` on the property; the backend calls that
 * method and returns the list. `optionsDependsOn` names the fields that should
 * trigger a refetch when they change, for example a credential or a schema
 * selection.
 *
 * Typing filters the list without preventing a value outside it, which covers
 * templates and tables the credential cannot list.
 */
export const NodeDynamicSelect = ({ property, values, nodeType }: NodeDynamicSelectProps) => {
  const [field, , helpers] = useField(property.name);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [options, setOptions] = useState<Option[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const requestIdRef = useRef(0);
  const latestValuesRef = useRef(values);
  latestValuesRef.current = values;

  const dependsOn: string[] = property.optionsDependsOn || [];
  const optionalDependsOn: string[] = property.optionsOptionalDependsOn || [];
  const dependencyValues = [...dependsOn, ...optionalDependsOn].map((name) => values[name]);
  const dependencyKey = JSON.stringify(dependencyValues);
  const missingDependency = dependsOn.find((name) => !values[name]);

  const isMultiple = Boolean(property.multiple);

  const currentValue = field.value ?? property?.default ?? "";

  // Multiple selection is stored as a comma separated string, which is what the
  // backend already splits on.
  const selectedValues: string[] = isMultiple
    ? String(currentValue)
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean)
    : [];

  const toggleValue = (value: string) => {
    const next = selectedValues.includes(value)
      ? selectedValues.filter((entry) => entry !== value)
      : [...selectedValues, value];
    helpers.setValue(next.join(", "));
  };

  const fetchOptions = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    if (!nodeType || !property.optionsMethod || missingDependency) {
      setOptions([]);
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
        setOptions(response?.options ?? []);
      }
    } catch (err: any) {
      if (requestId === requestIdRef.current) {
        setError(err?.message ?? "Could not load the list");
        setOptions([]);
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [dependencyKey, missingDependency, nodeType, property.name, property.optionsMethod]);

  useEffect(() => {
    fetchOptions();
  }, [fetchOptions]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Typing narrows the list without preventing a value outside it. In multiple
  // mode the box holds the selection, so the list is never filtered by it.
  const filtered =
    !isMultiple && currentValue
      ? options.filter((option) =>
          option.label.toLowerCase().includes(String(currentValue).toLowerCase())
        )
      : options;

  const helperText = (() => {
    if (loading) return "Loading the list...";
    if (missingDependency) {
      const label = missingDependency.replace(/_/g, " ").replace(/ id$/, "");
      return `Select ${label} to see the list. A name can still be typed.`;
    }
    if (error) return error;
    if (isMultiple && selectedValues.length > 0) {
      return `${selectedValues.length} of ${options.length} selected`;
    }
    if (options.length > 0) return `${options.length} available`;
    return null;
  })();

  return (
    <div
      className={`${property?.colSpan ? `col-span-${property?.colSpan}` : "col-span-2"}`}
      key={property.name}
    >
      <FieldLabel label={property.displayName} helpText={getFieldHelpText(property)} />

      <div className="relative" ref={containerRef}>
        <div className="flex gap-2">
          <div className="relative flex-1">
            {isMultiple ? (
              <button
                type="button"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                onMouseDown={(e: any) => e.stopPropagation()}
                aria-haspopup="listbox"
                aria-expanded={dropdownOpen}
                className="kai-node-field-control flex min-h-[46px] flex-wrap items-center gap-1.5 py-2 pl-3 pr-10 text-left"
              >
                {selectedValues.length === 0 && (
                  <span className="text-sm text-[var(--kai-placeholder)]">
                    {property.placeholder ?? "Select"}
                  </span>
                )}
                {selectedValues.map((value) => (
                  <span
                    key={value}
                    className="inline-flex items-center gap-1 rounded bg-[var(--kai-accent-soft)] px-2 py-0.5 text-xs text-[var(--kai-accent-text)]"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleValue(value);
                    }}
                  >
                    {value}
                    <X size={11} />
                  </span>
                ))}
              </button>
            ) : (
              <input
                type="text"
                value={currentValue}
                placeholder={property.placeholder ?? "Select or type"}
                onChange={(e) => {
                  helpers.setValue(e.target.value);
                  setDropdownOpen(true);
                }}
                onFocus={() => setDropdownOpen(true)}
                onMouseDown={(e: any) => e.stopPropagation()}
                className="kai-node-field-control py-3 pl-4 pr-10"
              />
            )}
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setDropdownOpen(!dropdownOpen)}
              onMouseDown={(e: any) => e.stopPropagation()}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-[var(--kai-text-muted)] transition-colors hover:bg-[var(--kai-surface-hover)] hover:text-[var(--kai-text)]"
            >
              <ChevronDown
                size={16}
                className={`transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`}
              />
            </button>

            {dropdownOpen && filtered.length > 0 && (
              <div className="kai-node-field-menu absolute left-0 right-0 z-50 mt-1 max-h-64 overflow-y-auto" role="listbox">
                {filtered.map((option) => {
                  const selected = isMultiple
                    ? selectedValues.includes(option.value)
                    : currentValue === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        if (isMultiple) {
                          toggleValue(option.value);
                        } else {
                          helpers.setValue(option.value);
                          setDropdownOpen(false);
                        }
                      }}
                      onMouseDown={(e: any) => e.stopPropagation()}
                      role="option"
                      aria-selected={selected}
                      className={`kai-node-field-option flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-sm ${selected ? "is-selected" : ""}`}
                    >
                      <span className="min-w-0 text-left">
                        <span className="block truncate">{option.label}</span>
                        {option.description && <span className="block truncate text-xs text-[var(--kai-text-muted)]">{option.description}</span>}
                      </span>
                      {selected && <Check size={14} />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <button
            type="button"
            title="Reload the list"
            disabled={loading || !!missingDependency}
            onClick={fetchOptions}
            onMouseDown={(e: any) => e.stopPropagation()}
            className="kai-node-field-action px-3"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>

      </div>

      {helperText && (
        <div
          className={`mt-1.5 flex items-start gap-1.5 text-xs ${error ? "text-[var(--kai-warning)]" : "text-[var(--kai-text-muted)]"}`}
        >
          {error && <AlertCircle size={13} className="mt-0.5 shrink-0" />}
          <span>{helperText}</span>
        </div>
      )}
    </div>
  );
};

export default NodeDynamicSelect;
