import React, { useState, useEffect } from "react";
import { AlertCircle, CheckCircle, Code } from "./Icon";

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
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
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
        <label className="text-white text-xs font-medium block">
          {label}
          {required && <span className="text-red-400 ml-1">*</span>}
        </label>
      )}

      {description && <p className="text-xs text-slate-400">{description}</p>}

      <div className="relative">
        <textarea
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          style={{ height: `${height}px` }}
          className={`
            w-full px-3 py-2 text-xs font-mono
            bg-slate-900/80 border rounded-lg
            text-white placeholder-slate-500
            focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500
            transition-all duration-200
            resize-none
            ${displayError ? "border-red-500" : "border-slate-600/50"}
            ${isValid ? "" : "border-red-500"}
          `}
        />

        {/* Format button */}
        <button
          type="button"
          onClick={handleFormat}
          className="absolute top-2 right-2 p-1 rounded bg-slate-700/50 hover:bg-slate-600/50 transition-colors"
          title="Format JSON"
        >
          <Code className="w-3 h-3 text-slate-400" />
        </button>

        {/* Validation indicator */}
        <div className="absolute top-2 right-8 flex items-center">
          {isValid && value.trim() ? (
            <CheckCircle className="w-3 h-3 text-green-400" />
          ) : !isValid ? (
            <AlertCircle className="w-3 h-3 text-red-400" />
          ) : null}
        </div>
      </div>

      {/* Error message */}
      {displayError && (
        <div className="flex items-center space-x-1 text-xs text-red-400">
          <AlertCircle className="w-3 h-3" />
          <span>{displayError}</span>
        </div>
      )}

      {/* Help text */}
      {!displayError && value.trim() && isValid && (
        <div className="flex items-center space-x-1 text-xs text-green-400">
          <CheckCircle className="w-3 h-3" />
          <span>Valid JSON</span>
        </div>
      )}
    </div>
  );
}
