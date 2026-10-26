import type { NodeProperty } from "../types";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";
import { VariableAutocompleteField } from "./VariableAutocompleteField";

interface NodeTextProps {
  property: NodeProperty;
  values: any;
}

export const NodeText = ({ property, values }: NodeTextProps) => {
  const displayOptions = property?.displayOptions || {};
  const show = displayOptions.show || {};

  if (Object.keys(show).length > 0) {
    for (const [dependencyName, validValue] of Object.entries(show)) {
      const dependencyValue = values[dependencyName];
      const matches =
        validValue === "*"
          ? dependencyValue !== undefined &&
            dependencyValue !== null &&
            dependencyValue !== ""
          : Array.isArray(validValue)
            ? validValue.includes(dependencyValue)
            : dependencyValue === validValue;
      if (!matches) {
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
        name={property.name}
        className="kai-node-field-control px-4 py-3"
        placeholder={property.placeholder}
      />
    </div>
  );
};
