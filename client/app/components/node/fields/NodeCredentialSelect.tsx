import CredentialSelector from "../../credentials/CredentialSelector";
import { getUserCredentialById } from "~/services/userCredentialService";
import type { NodeProperty } from "../types";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

interface NodeCredentialSelectProps {
  property: NodeProperty;
  values: any;
  setFieldValue: (name: string, value: any) => void;
}

export const NodeCredentialSelect = ({ property, values, setFieldValue }: NodeCredentialSelectProps) => {
  const handleCredentialChange = async (credentialId: string) => {
    const targetFieldName = property.name || "credential_id";
    setFieldValue(targetFieldName, credentialId);

    if (property.serviceType === "postgresql_vectorstore") {
      setFieldValue("connection_string", credentialId);
    }
    if (credentialId) {
      try {
        const result = await getUserCredentialById(credentialId);

        if ((result as any)?.secret?.api_key) {
          setFieldValue("tavily_api_key", (result as any).secret.api_key);
        }
      } catch (e) {
        console.error("Failed to fetch credential secret:", e);
      }
    }
  };

  const handleCredentialLoad = (secret: any) => {
    if (secret?.api_key) {
      setFieldValue("tavily_api_key", secret.api_key);
    }
  };

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
      <CredentialSelector
        value={values[property.name] ?? values.credential_id}
        onChange={handleCredentialChange}
        onCredentialLoad={handleCredentialLoad}
        serviceType={property.serviceType}
        placeholder={property.placeholder}
        showCreateNew={true}
        className="text-sm text-white px-4 py-3 rounded-lg w-full bg-slate-900/80 border"
      />
    </div>
  );
};
