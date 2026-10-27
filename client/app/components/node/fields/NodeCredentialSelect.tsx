import CredentialSelector from "../../credentials/CredentialSelector";
import type { NodeProperty } from "../types";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

interface NodeCredentialSelectProps {
  property: NodeProperty;
  values: any;
  setFieldValue: (name: string, value: any) => void;
}

export const NodeCredentialSelect = ({ property, values, setFieldValue }: NodeCredentialSelectProps) => {
  const handleCredentialChange = (credentialId: string) => {
    const targetFieldName = property.name || "credential_id";
    setFieldValue(targetFieldName, credentialId);

    if (property.serviceType === "postgresql_vectorstore") {
      setFieldValue("connection_string", credentialId);
    }
  };

  const handleCredentialLoad = (secret: any) => {
    if (property.serviceType === "mcp" && secret) {
      if (secret.test_endpoint_url) {
        setFieldValue("endpoint_url", secret.test_endpoint_url);
      }
      if (secret.test_transport) {
        setFieldValue("transport", secret.test_transport);
      }
    }
  };

  const displayOptions = property?.displayOptions || {};
  const show = displayOptions.show || {};

  if (Object.keys(show).length > 0) {
    for (const [dependencyName, validValue] of Object.entries(show)) {
      const dependencyValue = values[dependencyName];
      if (Array.isArray(validValue) ? !validValue.includes(dependencyValue) : dependencyValue !== validValue) {
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
      <CredentialSelector
        value={values[property.name] ?? values.credential_id}
        onChange={handleCredentialChange}
        onCredentialLoad={property.serviceType === "mcp" ? handleCredentialLoad : undefined}
        serviceType={property.serviceType}
        includeGenericFallback={!["mcp", "github"].includes(property.serviceType || "")}
        allowNone={property.serviceType === "mcp"}
        placeholder={property.placeholder}
        showCreateNew={true}
        appearance="dark"
      />
    </div>
  );
};
