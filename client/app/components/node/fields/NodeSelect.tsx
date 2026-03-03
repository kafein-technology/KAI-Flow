import { useField } from "formik";
import { useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";
import type { NodeProperty } from "../types";

interface NodeSelectProps {
  property: NodeProperty;
  values: any;
}

export const NodeSelect = ({ property, values }: NodeSelectProps) => {
  const [field, , helpers] = useField(property.name);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const displayOptions = property?.displayOptions || {};
  const show = displayOptions.show || {};

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (Object.keys(show).length > 0) {
    for (const [dependencyName, validValue] of Object.entries(show)) {
      const dependencyValue = values[dependencyName];
      if (dependencyValue !== validValue) {
        return null;
      }
    }
  }

  const currentValue = field.value ?? property?.default;
  const selectedOption = property.options?.find(
    (option: { value: string }) => option.value === currentValue
  );
  const displayText = selectedOption?.label || "Select...";

  const handleSelect = (value: string) => {
    helpers.setValue(value);
    setDropdownOpen(false);
  };

  return (
    <div className={`${property?.colSpan ? `col-span-${property?.colSpan}` : 'col-span-2'}`} key={property.name}>
      <label className="text-white text-sm font-medium mb-2 block">
        {property.displayName}
      </label>

      {/* Custom Dropdown */}
      <div className="relative" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setDropdownOpen(!dropdownOpen)}
          onMouseDown={(e: any) => e.stopPropagation()}
          onTouchStart={(e: any) => e.stopPropagation()}
          className={`w-full flex items-center justify-between bg-[#10182c] border border-slate-600 rounded-lg px-4 py-3 text-left transition-all duration-200 cursor-pointer hover:border-slate-500 ${
            dropdownOpen ? "border-blue-500" : ""
          }`}
        >
          <span className="text-sm text-white">{displayText}</span>
          <ChevronDown
            size={16}
            className={`text-slate-400 transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`}
          />
        </button>

        {/* Dropdown Menu */}
        {dropdownOpen && (
          <div className="absolute z-50 mt-1 left-0 right-0 bg-slate-900 border border-slate-700 rounded-lg shadow-lg shadow-black/40 overflow-hidden">
            {property.options?.map((option: { label: string; value: string; hint: string }) => (
              <button
                key={option.value}
                type="button"
                onClick={() => handleSelect(option.value)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left transition-colors duration-150 ${
                  currentValue === option.value
                    ? "bg-blue-500/20 text-blue-300"
                    : "text-slate-300 hover:bg-blue-500/20 hover:text-blue-300"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {property.hint && (
        <p className="text-slate-400 text-sm mt-1">{property.hint}</p>
      )}
      {selectedOption?.hint && (
        <p className="text-slate-400 text-xs bg-slate-900/30 mt-1">{selectedOption.hint}</p>
      )}
    </div>
  );
};
