import React, { useMemo, useState } from "react";
import { Formik, Form, Field, ErrorMessage } from "formik";
import { Check, Loader2, X as XIcon, Zap } from "lucide-react";
import { resolveIconPath } from "~/lib/iconUtils";
import type { ServiceDefinition, ServiceField } from "~/types/credentials";
import CredentialPasswordField from "./CredentialPasswordField";

interface DynamicCredentialFormProps {
  service: ServiceDefinition;
  onSubmit: (values: any) => void;
  onCancel: () => void;
  onTest?: (data: Record<string, any>) => Promise<{ success: boolean; message: string }>;
  initialValues?: Record<string, any>;
  isSubmitting?: boolean;
}

type TestState = "idle" | "loading" | "success" | "error";

const trimCredentialValues = (values: Record<string, any>) =>
  Object.fromEntries(
    Object.entries(values).map(([key, value]) => [
      key,
      typeof value === "string" ? value.trim() : value,
    ])
  );

const formatCredentialTestError = (
  message: string,
  serviceId: string,
  values: Record<string, any>
) => {
  const lower = message.toLowerCase();
  const baseUrl = String(values.base_url || "").toLowerCase();
  const isOpenRouter =
    serviceId === "openai_compatible" && baseUrl.includes("openrouter");

  if (
    isOpenRouter &&
    ["402", "insufficient", "quota", "credit", "billing", "payment"].some(
      (token) => lower.includes(token)
    )
  ) {
    return `${message} OpenRouter keys are not free — add credits at https://openrouter.ai/credits.`;
  }

  if (
    ["401", "unauthorized", "invalid_api_key", "invalid api key", "authentication"].some(
      (token) => lower.includes(token)
    )
  ) {
    return isOpenRouter
      ? `${message} Check your OpenRouter API key at https://openrouter.ai/keys — it may have changed or been revoked.`
      : `${message} Verify the API key is correct and has not changed.`;
  }

  if (
    lower.includes("model") &&
    ["not found", "does not exist", "invalid", "unknown"].some((token) =>
      lower.includes(token)
    )
  ) {
    return `${message} Check that the Model Name is correct for your provider.`;
  }

  return message;
};

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
    if (field.required) {
      const normalized =
        typeof value === "string" ? value.trim() : value;
      if (!normalized) {
        return `${field.label} is required`;
      }
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
    const values: Record<string, any> = {
      ...initialValues,
    };

    // Apply service fields's default values to Formik state
    service.fields.forEach((field) => {
      if (values[field.name] === undefined && field.default !== undefined) {
        values[field.name] = field.default;
      }
    });

    return values;
  }, [initialValues, service]);

  const renderField = (field: ServiceField) => {
    const commonProps = {
      name: field.name,
      placeholder: field.placeholder,
      className:
        "input w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200",
    };

    switch (field.type) {
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
            className="select w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 cursor-pointer"
          >
            <option value="">Select {field.label}</option>
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
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
            <span className="text-sm text-gray-700">{field.label}</span>
          </label>
        );

      default:
        return <Field type="text" {...commonProps} />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Service Header */}
      <div className="text-center pb-6 border-b border-gray-200">
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
        <h3 className="text-xl font-semibold text-gray-900 mb-2">
          Connect to {service.name}
        </h3>
        <p className="text-gray-600 text-sm max-w-md mx-auto">
          {service.description}
        </p>
        {service.id === "openai_compatible" && (
          <p className="text-amber-700 text-xs max-w-md mx-auto mt-3 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            OpenRouter and similar providers require a paid or credited API key.
            Use show/hide on the API key field to verify it, then run Test
            Connection before saving. Add credits at{" "}
            <a
              href="https://openrouter.ai/credits"
              target="_blank"
              rel="noopener noreferrer"
              className="underline font-medium"
            >
              openrouter.ai/credits
            </a>
            .
          </p>
        )}
      </div>

      <Formik
        initialValues={formValues}
        validate={validateForm}
        onSubmit={(values) => onSubmit(trimCredentialValues(values))}
        enableReinitialize
      >
        {({ values, errors, touched, handleChange, handleBlur }) => (
          <Form className="space-y-6">
            {/* Credential Name */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                Name <span className="text-red-500">*</span>
              </label>
              <Field
                name="name"
                type="text"
                placeholder={`${service.name} Credential`}
                className="input w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
              />
              <ErrorMessage
                name="name"
                component="p"
                className="text-red-500 text-sm mt-1"
              />
            </div>

            {service.fields.map((field) => {
              if (!isFieldVisible(field, values)) return null;

              return (
                <div key={field.name} className="space-y-2">
                  {field.type !== "checkbox" && (
                    <label className="block text-sm font-medium text-gray-700">
                      {field.label}
                      {field.required && (
                        <span className="text-red-500 ml-1">*</span>
                      )}
                    </label>
                  )}

                  {renderField(field)}

                  {field.description && (
                    <p className="text-xs text-gray-500 mt-1">
                      {field.description}
                    </p>
                  )}

                  <ErrorMessage
                    name={field.name}
                    component="p"
                    className="text-red-500 text-sm mt-1"
                  />
                </div>
              );
            })}

            {/* Test result message */}
            {testMessage && testState !== "loading" && (
              <p className={`text-sm ${testState === "success" ? "text-green-600" : "text-red-500"}`}>
                {testMessage}
              </p>
            )}

            {/* Form Actions */}
            <div className="flex items-center justify-end gap-3 pt-6 border-t border-gray-200">
              <button
                type="button"
                onClick={onCancel}
                className="px-6 py-2.5 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-all duration-200"
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
                    const trimmedValues = trimCredentialValues(values);
                    try {
                      const result = await onTest(trimmedValues);
                      setTestState(result.success ? "success" : "error");
                      setTestMessage(
                        result.success
                          ? result.message
                          : formatCredentialTestError(
                              result.message,
                              service.id,
                              trimmedValues
                            )
                      );
                    } catch (error: any) {
                      setTestState("error");
                      setTestMessage(
                        formatCredentialTestError(
                          error?.message || "Unexpected error. Please try again.",
                          service.id,
                          trimmedValues
                        )
                      );
                    }
                    setTimeout(() => {
                      setTestState("idle");
                      setTestMessage("");
                    }, 8000);
                  }}
                  className={`flex items-center gap-1.5 px-5 py-2.5 rounded-lg border transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed
                    ${testState === "success"
                      ? "text-green-600 border-green-300 bg-green-50"
                      : testState === "error"
                        ? "text-red-500 border-red-300 bg-red-50"
                        : "text-gray-700 border-gray-300 bg-white hover:bg-gray-50"
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
                className="px-6 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
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