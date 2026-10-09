import { useField } from "formik";
import type { NodeProperty } from "../types";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";
import { ThemedNumberInput } from "./ThemedNumberInput";

interface NodeNumberProps {
  property: NodeProperty;
  values: any;
}

const BYTES_PER_MB = 1024 * 1024;

function numberScale(property: NodeProperty): number {
  return property.unit === "MB" ? BYTES_PER_MB : 1;
}

function displayNumber(property: NodeProperty, value: unknown): number | "" {
  if (value === "" || value === null || value === undefined) return "";
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed / numberScale(property) : "";
}

function storedNumber(property: NodeProperty, value: unknown): number | "" {
  if (value === "" || value === null || value === undefined) return "";
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.round(parsed * numberScale(property)) : "";
}

function displayConstraint(
  property: NodeProperty,
  value: unknown,
): number | undefined {
  const displayed = displayNumber(property, value);
  return displayed === "" ? undefined : displayed;
}

export const NodeNumber = ({ property, values }: NodeNumberProps) => {
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

  return (
    <div className={`${property?.colSpan ? `col-span-${property?.colSpan}` : 'col-span-2'}`} key={property.name}>
      <FieldLabel
        label={property.displayName}
        helpText={getFieldHelpText(property)}
      />
      <div className={property.unit ? "flex items-center gap-2" : undefined}>
        <ThemedNumberInput
          name={property.name}
          value={
            property.unit
              ? displayNumber(property, field.value ?? property.default)
              : field.value ?? property.default ?? ""
          }
          min={
            property.unit
              ? displayConstraint(property, property.min)
              : property.min
          }
          max={
            property.unit
              ? displayConstraint(property, property.max)
              : property.max
          }
          step={
            property.unit
              ? displayConstraint(property, property.step ?? 1)
              : property.step
          }
          placeholder={property?.placeholder}
          ariaLabel={property.displayName}
          onBlur={field.onBlur}
          onChange={(nextValue) =>
            helpers.setValue(
              property.unit ? storedNumber(property, nextValue) : nextValue,
            )
          }
          className={property.unit ? "flex-1" : "w-full"}
        />
        {property.unit && (
          <span className="shrink-0 text-sm text-slate-400">{property.unit}</span>
        )}
      </div>
    </div>
  );
};
