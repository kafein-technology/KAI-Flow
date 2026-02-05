import { useField } from "formik";
import type { NodeProperty } from "../types";
import { ErrorMessage } from "formik";

interface NodeCheckboxProps {
  property: NodeProperty;
  values: any;
}

export const NodeCheckbox = ({ property, values }: NodeCheckboxProps) => {
  const [field, , helpers] = useField(property.name);
  const displayOptions = property?.displayOptions || {};
  const show = displayOptions.show || {};

  if (Object.keys(show).length > 0) {
    for (const [dependencyName, validValue] of Object.entries(show)) {
      const dependencyValue = values[dependencyName];
      if (dependencyValue !== validValue) {
        return null;
      }
    }
  }

  const isChecked = Boolean(field.value);

  return (
    <div className={`${property?.colSpan ? `col-span-${property?.colSpan}` : 'col-span-2'}`} key={property.name}>
      <div className="flex items-center justify-between">
        <div className="flex flex-col">
          <span className="text-sm text-slate-200">{property.displayName}</span>
          {property.hint && (
            <span className="text-xs text-slate-400">{property.hint}</span>
          )}
        </div>
        {/* Toggle Switch */}
        <button
          type="button"
          onClick={() => helpers.setValue(!isChecked)}
          onMouseDown={(e: any) => e.stopPropagation()}
          onTouchStart={(e: any) => e.stopPropagation()}
          className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${
            isChecked ? "bg-blue-500" : "bg-slate-600"
          }`}
        >
          <span
            className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform duration-200 ${
              isChecked ? "translate-x-5" : "translate-x-0"
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
