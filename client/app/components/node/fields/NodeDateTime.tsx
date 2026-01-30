import { Field } from "formik";
import type { NodeProperty } from "../types";
import { CalendarDays } from "../../common/Icon";

interface NodeDateTimeProps {
  property: NodeProperty;
  values: any;
}

export const NodeDateTime = ({ property, values }: NodeDateTimeProps) => {
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
      <div className="flex items-center space-x-2 mb-2">
        <CalendarDays className="w-4 h-4 text-green-400" />
        <label className="text-white text-sm font-medium">
          {property.displayName}
        </label>
      </div>
      <Field
        className="w-full bg-slate-900/80 border border-slate-600/50 rounded-lg text-white placeholder-slate-400 px-3 py-2 text-sm focus:border-green-500 focus:ring-2 focus:ring-green-500/20 transition-all"
        type="datetime-local"
        name={property.name}
      />
      {property.hint && (
        <p className="text-slate-400 text-sm mt-1">{property.hint}</p>
      )}
    </div>
  );
};
