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

  const dependsOn: string[] = property.optionsDependsOn || [];
  const dependencyValues = dependsOn.map((name) => values[name]);
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
    if (!nodeType || !property.optionsMethod || missingDependency) {
      setOptions([]);
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

      setOptions(response?.options ?? []);
    } catch (err: any) {
      setError(err?.message ?? "Could not load the list");
      setOptions([]);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeType, property.name, ...dependencyValues]);

  useEffect(() => {
    fetchOptions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencyValues]);

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
                className="w-full min-h-[46px] flex flex-wrap items-center gap-1.5 bg-[#10182c] border border-slate-600 rounded-lg pl-3 pr-10 py-2 text-left focus:border-blue-500 focus:outline-none transition-colors"
              >
                {selectedValues.length === 0 && (
                  <span className="text-sm text-slate-500">
                    {property.placeholder ?? "Select"}
                  </span>
                )}
                {selectedValues.map((value) => (
                  <span
                    key={value}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 text-xs"
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
                className="w-full bg-[#10182c] border border-slate-600 rounded-lg pl-4 pr-10 py-3 text-sm text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none transition-colors"
              />
            )}
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setDropdownOpen(!dropdownOpen)}
              onMouseDown={(e: any) => e.stopPropagation()}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-200"
            >
              <ChevronDown
                size={16}
                className={`transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`}
              />
            </button>
          </div>

          <button
            type="button"
            title="Reload the list"
            disabled={loading || !!missingDependency}
            onClick={fetchOptions}
            onMouseDown={(e: any) => e.stopPropagation()}
            className={`px-3 rounded-lg border transition-colors ${
              loading || missingDependency
                ? "border-slate-700 text-slate-600 cursor-not-allowed"
                : "border-slate-600 text-slate-400 hover:text-blue-300 hover:border-blue-500"
            }`}
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>

        {dropdownOpen && filtered.length > 0 && (
          <div className="absolute z-50 mt-1 left-0 right-0 max-h-64 overflow-y-auto bg-slate-900 border border-slate-700 rounded-lg shadow-lg shadow-black/40">
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
                  className={`w-full flex items-center justify-between gap-3 px-4 py-2.5 text-sm text-left transition-colors duration-150 ${
                    selected
                      ? "bg-blue-500/20 text-blue-300"
                      : "text-slate-300 hover:bg-blue-500/20 hover:text-blue-300"
                  }`}
                >
                  <span>{option.label}</span>
                  {selected && <Check size={14} />}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {helperText && (
        <div
          className={`flex items-start gap-1.5 mt-1.5 text-xs ${
            error ? "text-amber-400" : "text-slate-500"
          }`}
        >
          {error && <AlertCircle size={13} className="mt-0.5 shrink-0" />}
          <span>{helperText}</span>
        </div>
      )}
    </div>
  );
};

export default NodeDynamicSelect;
