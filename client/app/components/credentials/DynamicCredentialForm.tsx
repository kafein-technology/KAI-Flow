import React, { useMemo, useState } from "react";
import { Formik, Form, Field, ErrorMessage } from "formik";
import { resolveIconPath } from "~/lib/iconUtils";
import type { ServiceDefinition, ServiceField } from "~/types/credentials";

interface DynamicCredentialFormProps {
  service: ServiceDefinition;
  onSubmit: (values: any) => void;
  onCancel: () => void;
  initialValues?: Record<string, any>;
  isSubmitting?: boolean;
}

const DynamicCredentialForm: React.FC<DynamicCredentialFormProps> = ({
  service,
  onSubmit,
  onCancel,
  initialValues = {},
  isSubmitting = false,
}) => {
  const [iconFailed, setIconFailed] = useState(false);
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
          <Field type="password" {...commonProps} autoComplete="new-password" />
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
      </div>

      <Formik
        initialValues={formValues}
        validate={validateForm}
        onSubmit={onSubmit}
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
                  <label className="block text-sm font-medium text-gray-700">
                    {field.label}
                    {field.required && (
                      <span className="text-red-500 ml-1">*</span>
                    )}
                  </label>

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

            {/* Form Actions */}
            <div className="flex items-center justify-end gap-3 pt-6 border-t border-gray-200">
              <button
                type="button"
                onClick={onCancel}
                className="px-6 py-2.5 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-all duration-200"
              >
                Cancel
              </button>
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
