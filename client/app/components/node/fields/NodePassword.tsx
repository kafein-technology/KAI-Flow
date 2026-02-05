import { Field } from "formik";
import type { NodeProperty } from "../types";

interface NodePasswordProps {
  property: NodeProperty;
  values: any;
}

export const NodePassword = ({ property, values }: NodePasswordProps) => {
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
      <label className="text-white text-sm font-medium mb-2 block">
        {property.displayName}
      </label>
      <Field
        type="password"
        name={property.name}
        className="input input-bordered w-full bg-[#10182c] text-white text-sm rounded-lg px-4 py-3 border border-slate-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20"
        placeholder={property.placeholder}
      />
      {property.hint && (
        <p className="text-slate-400 text-sm mt-1">{property.hint}</p>
      )}
    </div>
  );
};
