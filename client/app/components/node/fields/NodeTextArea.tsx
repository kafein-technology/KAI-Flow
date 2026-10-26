import { ErrorMessage } from "formik";
import type { NodeProperty } from "../types";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";
import { VariableAutocompleteField } from "./VariableAutocompleteField";

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
      <FieldLabel
        label={property.displayName}
        helpText={getFieldHelpText(property)}
      />
      <VariableAutocompleteField
        as="textarea"
        name={property.name}
        placeholder={property.placeholder}
        rows={property.rows}
        className="kai-node-field-control resize-y px-4 py-3"
        onMouseDown={(e: any) => e.stopPropagation()}
        onTouchStart={(e: any) => e.stopPropagation()}
      />
      <ErrorMessage
        name={property.name}
        component="div"
        className="kai-node-field-error mt-1"
      />
      {property.maxLength && (
        <div className="kai-node-field-hint mt-1">
          Characters: {property.value?.length.toLocaleString() || 0} /{" "}
          {property.maxLength.toLocaleString()}
        </div>
      )}
    </div>
  );
};
