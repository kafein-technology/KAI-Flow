import React, { useState, useEffect } from "react";
import { AlertCircle, CheckCircle, Code } from "lucide-react";
import { VariableAutocompleteControl } from "../node/fields/VariableAutocompleteField";

interface JSONEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  height?: number;
  label?: string;
  description?: string;
  required?: boolean;
  error?: string;
  className?: string;
}

export default function JSONEditor({
  value,
  onChange,
  placeholder = "{}",
  height = 120,
  label,
  description,
  required = false,
  error,
  className = "",
}: JSONEditorProps) {
  const [isValid, setIsValid] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);

  // JSON validation
  const validateJSON = (jsonString: string): boolean => {
    if (!jsonString.trim()) {
      setLocalError(null);
      return true;
    }

    try {
      JSON.parse(jsonString);
      setLocalError(null);
      return true;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Invalid JSON";
      setLocalError(errorMessage);
      return false;
    }
  };

  // Auto-format JSON
  const formatJSON = (jsonString: string): string => {
    if (!jsonString.trim()) return jsonString;

    try {
      const parsed = JSON.parse(jsonString);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return jsonString;
    }
  };

  // Handle input change
  const handleChange = (newValue: string) => {
    const valid = validateJSON(newValue);
    setIsValid(valid);
    onChange(newValue);
  };

  // Handle format button click
  const handleFormat = () => {
    const formatted = formatJSON(value);
    onChange(formatted);
    setIsValid(true);
    setLocalError(null);
  };

  // Validate on mount and when value changes
  useEffect(() => {
    validateJSON(value);
  }, [value]);

  const displayError = error || localError;

  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <label className="block text-xs font-medium text-[var(--kai-text-soft)]">
          {label}
          {required && <span className="ml-1 text-[var(--kai-danger-text-soft)]">*</span>}
        </label>
      )}

      {description && <p className="kai-node-field-hint">{description}</p>}

      <div className="relative">
        <VariableAutocompleteControl
          name="json"
          as="textarea"
          value={value}
          onValueChange={handleChange}
          placeholder={placeholder}
          style={{ height: `${height}px` }}
          className={`
            kai-node-field-control w-full resize-none px-3 py-2 text-xs font-mono
            ${displayError || !isValid ? "!border-[var(--kai-danger)] focus:!border-[var(--kai-danger)] focus:!shadow-[0_0_0_3px_var(--kai-danger-subtle)]" : ""}
          `}
        />

        {/* Format button */}
        <button
          type="button"
          onClick={handleFormat}
          className="absolute right-2 top-2 rounded border border-[var(--kai-control-border)] bg-[var(--kai-surface-control)] p-1 transition-colors hover:bg-[var(--kai-surface-hover)]"
          title="Format JSON"
        >
          <Code className="h-3 w-3 text-[var(--kai-text-muted)]" />
        </button>

        {/* Validation indicator */}
        <div className="absolute top-2 right-8 flex items-center">
          {isValid && value.trim() ? (
            <CheckCircle className="h-3 w-3 text-[var(--kai-success-text)]" />
          ) : !isValid ? (
            <AlertCircle className="h-3 w-3 text-[var(--kai-danger-text-soft)]" />
          ) : null}
        </div>
      </div>

      {/* Error message */}
      {displayError && (
        <div className="kai-node-field-error flex items-center space-x-1">
          <AlertCircle className="w-3 h-3" />
          <span>{displayError}</span>
        </div>
      )}

      {/* Help text */}
      {!displayError && value.trim() && isValid && (
        <div className="flex items-center space-x-1 text-xs text-[var(--kai-success-text)]">
          <CheckCircle className="w-3 h-3" />
          <span>Valid JSON</span>
        </div>
      )}
    </div>
  );
}
