import { useField } from "formik";
import type { NodeProperty } from "../types";
import { ErrorMessage } from "formik";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

interface NodeCheckboxProps {
  property: NodeProperty;
  values: any;
}

export const NodeCheckbox = ({ property, values }: NodeCheckboxProps) => {
  const [field, , helpers] = useField(property.name);
  const displayOptions = property?.displayOptions || {};
  const show = displayOptions.show || {};

  if (Object.keys(show).length > 0) {
    const compare = (name: string, expected: any) => {
      const current = values[name];
      if (expected === "*") {
        return current !== undefined && current !== null && current !== "";
      }
      return Array.isArray(expected) ? expected.includes(current) : current === expected;
    };

    for (const [dependencyName, validValue] of Object.entries(show)) {
      // "_any" holds alternatives; matching one of them is enough.
      const matches =
        dependencyName === "_any" && validValue && typeof validValue === "object"
          ? Object.entries(validValue).some(([name, expected]) => compare(name, expected))
          : compare(dependencyName, validValue);
      if (!matches) {
        return null;
      }
    }
  }

  const isChecked = Boolean(field.value);

  return (
    <div className={`${property?.colSpan ? `col-span-${property?.colSpan}` : 'col-span-2'}`} key={property.name}>
      <div className="flex items-center justify-between">
        <FieldLabel
          label={property.displayName}
          helpText={getFieldHelpText(property)}
          className="text-sm text-slate-200"
        />
        {/* Toggle Switch */}
        <button
          type="button"
          onClick={() => helpers.setValue(!isChecked)}
          onMouseDown={(e: any) => e.stopPropagation()}
          onTouchStart={(e: any) => e.stopPropagation()}
          className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${isChecked ? "bg-blue-500" : "bg-slate-600"
            }`}
        >
          <span
            className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform duration-200 ${isChecked ? "translate-x-5" : "translate-x-0"
              }`}
          />
        </button>
      </div>
      <ErrorMessage
        name={property.name}
        component="div"
        className="text-red-400 text-sm mt-1"
      />
    </div>
  );
};
