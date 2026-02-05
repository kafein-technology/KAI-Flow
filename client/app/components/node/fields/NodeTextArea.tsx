import { Field, ErrorMessage } from "formik";
import type { NodeProperty } from "../types";

interface NodeTextAreaProps {
  property: NodeProperty;
  values: any;
}

export const NodeTextArea = ({ property, values }: NodeTextAreaProps) => {
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

  return (
    <div className={`${property?.colSpan ? `col-span-${property?.colSpan}` : 'col-span-2'}`} key={property.name}>
      <label className="text-white text-sm font-medium mb-2 block flex items-center gap-2">
        {property.displayName}
      </label>
      <Field
        as="textarea"
        name={property.name}
        placeholder={property.placeholder}
        rows={property.rows}
        className="text-sm text-white px-4 py-3 rounded-lg w-full bg-[#10182c] border border-slate-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 resize-vertical"
        onMouseDown={(e: any) => e.stopPropagation()}
        onTouchStart={(e: any) => e.stopPropagation()}
      />
      <ErrorMessage
        name={property.name}
        component="div"
        className="text-red-400 text-sm mt-1"
      />
      {property.hint && (
        <p className="text-slate-400 text-sm mt-1">{property.hint}</p>
      )}
      {property.maxLength && (
        <div className="text-gray-400 text-xs mt-1">
          Characters: {property.value?.length.toLocaleString() || 0} /{" "}
          {property.maxLength.toLocaleString()}
        </div>
      )}
    </div>
  );
};
