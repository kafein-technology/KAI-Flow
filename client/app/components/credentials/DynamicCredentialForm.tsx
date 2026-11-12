import React, { useMemo, useState } from "react";
import { Formik, Form, Field, ErrorMessage } from "formik";
import { Check, Loader2, X as XIcon, Zap } from "lucide-react";
import { resolveIconPath } from "~/lib/iconUtils";
import type { ServiceDefinition, ServiceField } from "~/types/credentials";
import CredentialPasswordField from "./CredentialPasswordField";
import CredentialModelCombobox from "./CredentialModelCombobox";

interface DynamicCredentialFormProps {
  service: ServiceDefinition;
  onSubmit: (values: any) => void;
  onCancel: () => void;
  onTest?: (data: Record<string, any>) => Promise<{ success: boolean; message: string }>;
  initialValues?: Record<string, any>;
  isSubmitting?: boolean;
}

type TestState = "idle" | "loading" | "success" | "error";

const DynamicCredentialForm: React.FC<DynamicCredentialFormProps> = ({
  service,
  onSubmit,
  onCancel,
  onTest,
  initialValues = {},
  isSubmitting = false,
}) => {
  const [iconFailed, setIconFailed] = useState(false);
  const [testState, setTestState] = useState<TestState>("idle");
  const [testMessage, setTestMessage] = useState("");

  const validateField = (
    field: ServiceField,
    value: any
  ): string | undefined => {
    if (field.required && !value) {
      return `${field.label} is required`;
    }

    if (value && field.validation) {
      const { minLength, maxLength, pattern, custom } = field.validation;

      if (minLength && value.length < minLength) {
        return `${field.label} must be at least ${minLength} characters`;
      }

      if (maxLength && value.length > maxLength) {
        return `${field.label} must be no more than ${maxLength} characters`;
      }

      if (pattern && !new RegExp(pattern).test(value)) {
        return `${field.label} format is invalid`;
      }

      if (custom) {
        return custom(value);
      }
    }

    return undefined;
  };

  const isFieldVisible = (
    field: ServiceField,
    values: Record<string, any>
  ): boolean => {
    if (!field.dependsOn) return true;
    const depValue = values[field.dependsOn.field];
    return field.dependsOn.values.includes(depValue);
  };

  const validateForm = (
    values: Record<string, any>
  ): Record<string, string> => {
    const errors: Record<string, string> = {};

    // Validate credential name
    if (!values.name || String(values.name).trim() === "") {
      errors.name = "Name is required";
    } else if (String(values.name).length > 100) {
      errors.name = "Name must be no more than 100 characters";
    }

    service.fields.forEach((field) => {
      // Skip validation for hidden fields
      if (!isFieldVisible(field, values)) return;

      const error = validateField(field, values[field.name]);
      if (error) {
        errors[field.name] = error;
      }
    });

    return errors;
  };

  const formValues = useMemo(() => {
    const values = {
      ...initialValues,
    };
    if (service.id === "decision_model" && values.base_url && values.endpoint_type === undefined) {
      values.endpoint_type = "/v1/systemone";
    }

    // Apply service fields's default values to Formik state
    service.fields.forEach((field) => {
      if (values[field.name] === undefined) {
        if (field.default !== undefined) values[field.name] = field.default;
        else if (service.id === "decision_model") values[field.name] = "";
      }
    });

    if (service.id === "decision_model") {
      if (values.endpoint_type === "systemone") values.endpoint_type = "/v1/systemone";
      if (values.endpoint_type === "decisions") values.endpoint_type = "/api/alpha/decisions";
      if (values.endpoint_type === "") values.endpoint_type = "custom";
    }

    return values;
  }, [initialValues, service]);

  const renderField = (
    field: ServiceField,
    values: Record<string, any>,
    setValue?: (name: string, value: any) => void,
  ) => {
    const commonProps = {
      name: field.name,
      placeholder: field.placeholder,
      className:
        "input w-full rounded-lg border border-[var(--kai-control-border)] bg-[var(--kai-surface-control)] px-4 py-3 text-zinc-100 placeholder:text-zinc-500 focus:border-[var(--kai-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--kai-accent)]/20",
    };

    switch (field.type) {
      case "model-combobox":
        return (
          <CredentialModelCombobox
            field={field}
            serviceType={service.id}
            values={values}
            className={commonProps.className}
          />
        );

      case "textarea":
        return (
          <Field
            as="textarea"
            {...commonProps}
            rows={4}
            className={`${commonProps.className} resize-none`}
          />
        );

      case "select":
        return (
          <Field
            as="select"
            name={field.name}
            {...(service.id === "decision_model" && field.name === "endpoint_type" ? {
              onChange: (event: React.ChangeEvent<HTMLSelectElement>) => {
                setValue?.("endpoint_type", event.target.value);
                setValue?.("model_name", "");
              },
            } : {})}
            className="select select-bordered w-full cursor-pointer rounded-lg border border-[var(--kai-control-border)] bg-[var(--kai-surface-control)] text-zinc-100 focus:border-[var(--kai-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--kai-accent)]/20"
          >
            {!(service.id === "decision_model" && field.name === "endpoint_type") && <option value="">Select {field.label}</option>}
            {field.options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Field>
        );

      case "password":
        return (
          <CredentialPasswordField
            name={field.name}
            placeholder={field.placeholder}
            className={commonProps.className}
          />
        );

      case "checkbox":
        return (
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <Field
              type="checkbox"
              name={field.name}
              className="h-4 w-4 cursor-pointer rounded border-[var(--kai-control-muted)] accent-[var(--kai-accent)] focus:ring-[var(--kai-accent)]"
            />
            <span className="text-sm text-zinc-200">{field.label}</span>
          </label>
        );

      default:
        return <Field type="text" {...commonProps} />;
    }
  };

  const renderServiceField = (
    field: ServiceField,
    values: Record<string, any>,
    setValue?: (name: string, value: any) => void,
  ) => {
    if (!isFieldVisible(field, values)) return null;
    return (
      <div key={field.name} className="space-y-2">
        {field.type !== "checkbox" && (
          <label className="block text-sm font-medium text-zinc-200">
            {field.label}
            {field.required && <span className="text-red-500 ml-1">*</span>}
          </label>
        )}
        {renderField(field, values, setValue)}
        {field.description && <p className="mt-1 text-xs text-zinc-400">{field.description}</p>}
        <ErrorMessage name={field.name} component="p" className="text-red-500 text-sm mt-1" />
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Service Header */}
      <div className="border-b border-[var(--kai-border-soft)] pb-6 text-center">
        {/* Service Icon (SVG with fallback) */}
        {(() => {
          const [failed, setFailed] = [iconFailed, setIconFailed];
          return (
            <div className="mb-3 flex items-center justify-center">
              {!failed && (
                <img
                  src={resolveIconPath(
                    service.icon
                      ? `icons/${service.icon}`
                      : `icons/${service.id}.svg`
                  )}
                  alt={`${service.name} logo`}
                  className="w-12 h-12 object-contain"
                  onError={() => setFailed(true)}
                />
              )}
              {failed && <div className="text-4xl">{service.icon}</div>}
            </div>
          );
        })()}
        <h3 className="mb-2 text-xl font-semibold text-white">
          Connect to {service.name}
        </h3>
        <p className="mx-auto max-w-md text-sm text-zinc-400">
          {service.description}
        </p>
      </div>

      <Formik
        initialValues={formValues}
        validate={validateForm}
        onSubmit={onSubmit}
        enableReinitialize
      >
        {({ values, errors, touched, handleChange, handleBlur, setFieldValue }) => (
          <Form className="space-y-6">
            {service.id === "decision_model" && renderServiceField(service.fields[0], values, setFieldValue)}
            {/* Credential Name */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-zinc-200">
                Name <span className="text-red-500">*</span>
              </label>
              <Field
                name="name"
                type="text"
                placeholder={`${service.name} Credential`}
                className="input w-full rounded-lg border border-[var(--kai-control-border)] bg-[var(--kai-surface-control)] px-4 py-3 text-zinc-100 placeholder:text-zinc-500 focus:border-[var(--kai-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--kai-accent)]/20"
              />
              <ErrorMessage
                name="name"
                component="p"
                className="text-red-500 text-sm mt-1"
              />
            </div>

            {service.fields
              .filter((field) => service.id !== "decision_model" || field.name !== "endpoint_type")
              .map((field) => renderServiceField(field, values, setFieldValue))}

            {/* Test result message */}
            {testMessage && testState !== "loading" && (
              <p className={`text-sm ${testState === "success" ? "text-green-600" : "text-red-500"}`}>
                {testMessage}
              </p>
            )}

            {/* Form Actions */}
            <div className="flex items-center justify-end gap-3 border-t border-[var(--kai-border-soft)] pt-6">
              <button
                type="button"
                onClick={onCancel}
                className="rounded-lg border border-[var(--kai-control-border)] bg-[var(--kai-surface-control)] px-6 py-2.5 text-zinc-100 transition-colors hover:border-[var(--kai-control-muted)] hover:bg-[var(--kai-surface-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--kai-accent)]"
              >
                Cancel
              </button>
              {onTest && (
                <button
                  type="button"
                  disabled={testState === "loading"}
                  onClick={async () => {
                    setTestState("loading");
                    setTestMessage("");
                    try {
                      const result = await onTest(values);
                      setTestState(result.success ? "success" : "error");
                      setTestMessage(
                        result.message ||
                          (result.success
                            ? "Connection successful."
                            : "Connection failed. Please check your connection details.")
                      );
                    } catch (error: any) {
                      setTestState("error");
                      setTestMessage(error?.message || "Connection failed. Please check your connection details.");
                    }
                    setTimeout(() => {
                      setTestState("idle");
                      setTestMessage("");
                    }, 4000);
                  }}
                  className={`flex items-center gap-1.5 px-5 py-2.5 rounded-lg border transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed
                    ${testState === "success"
                      ? "border-emerald-400/35 bg-emerald-400/10 text-emerald-300"
                      : testState === "error"
                        ? "border-red-400/35 bg-red-400/10 text-red-300"
                        : "border-[var(--kai-control-border)] bg-[var(--kai-surface-control)] text-zinc-100 hover:border-[var(--kai-accent)]/60 hover:bg-[var(--kai-accent)]/10"
                    }`}
                >
                  {testState === "loading" && <Loader2 className="w-4 h-4 animate-spin" />}
                  {testState === "success" && <Check className="w-4 h-4" />}
                  {testState === "error" && <XIcon className="w-4 h-4" />}
                  {testState === "idle" && <Zap className="w-4 h-4" />}
                  Test Connection
                </button>
              )}
              <button
                type="submit"
                disabled={isSubmitting}
                className="rounded-lg border border-[var(--kai-accent)] bg-[var(--kai-accent)] px-6 py-2.5 text-white transition-colors hover:border-[var(--kai-accent-hover)] hover:bg-[var(--kai-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--kai-accent)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSubmitting ? "Connecting..." : "Connect Service"}
              </button>
            </div>
          </Form>
        )}
      </Formik>
    </div>
  );
};

export default DynamicCredentialForm;
