import { Formik, Form } from "formik";
import type { GenericData, NodeProperty } from "./types";
import {
  NodeTextArea,
  NodeCredentialSelect,
  NodeText,
  NodeReadonlyText,
  NodeNumber,
  NodePassword,
  NodeSelect,
  NodeModelSelect,
  NodeCheckbox,
  NodeTitle,
  NodeRange,
  NodeJsonEditor,
  NodeDateTime,
  NodeCodeEditor,
  NodeSessionId,
  ThemedNumberInput,
  NodeModelArtifactSource,
} from "./fields";
import { FieldLabel, getFieldHelpText } from "./fields/FieldLabel";
import TabNavigation from "../common/TabNavigation";
import { useState, useRef, useEffect } from "react";
import { Settings, Plus, X, ChevronDown } from "lucide-react";
import { NodeDynamicSelect } from "./fields/NodeDynamicSelect";
import { NodeColumnMapper } from "./fields/NodeColumnMapper";
import { NodeDocumentEditor } from "./fields/NodeDocumentEditor";
import { NodeMcpParameters } from "./fields/NodeMcpParameters";
import { useVariableStore } from "~/stores/variables";

interface GenericNodeFormProps {
  initialValues?: GenericData;
  validate?: (values: Partial<GenericData>) => any;
  onSubmit?: (values: GenericData) => void;
  onCancel: () => void;
  configData?: any;
  onSave?: (values: any) => void;
  onChange?: (values: GenericData) => void;
  nodeId?: string;
}

const cleanValues = (obj: any): any => {
  if (obj === null || obj === undefined) return "";
  if (typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(cleanValues);

  const cleaned: any = {};
  const keys = Object.keys(obj).sort();
  for (const key of keys) {
    const val = cleanValues(obj[key]);
    if (val !== "" && val !== null && val !== undefined) {
      cleaned[key] = val;
    }
  }
  return cleaned;
};

function FormValuesObserver({
  values,
  initialValues,
  onChange,
}: {
  values: GenericData;
  initialValues: GenericData;
  onChange?: (values: GenericData) => void;
}) {
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const valuesKeyRef = useRef<string>("");

  useEffect(() => {
    // Compare cleaned values. If identical to cleaned initialValues, do not trigger onChange
    const cleanCurrent = cleanValues(values);
    const cleanInitial = cleanValues(initialValues);
    if (JSON.stringify(cleanCurrent) === JSON.stringify(cleanInitial)) {
      return;
    }

    const nextKey = JSON.stringify(values);
    if (valuesKeyRef.current === nextKey) return;
    valuesKeyRef.current = nextKey;
    onChangeRef.current?.(values);
  }, [values, initialValues]);

  return null;
}

export default function GenericNodeForm({
  initialValues: propInitialValues,
  validate: propValidate,
  onSubmit: propOnSubmit,
  onCancel,
  configData,
  nodeId,
  onSave,
  onChange,
}: GenericNodeFormProps) {
  const fetchVariables = useVariableStore((state) => state.fetchVariables);
  useEffect(() => {
    void fetchVariables().catch(() => {});
  }, [fetchVariables]);
  const rawProperties = configData?.metadata?.properties || [];
  const nodeType =
    configData?.metadata?.name || configData?.name || configData?.type;
  // OpenAI GPT and OpenAI Compatible take the model from the credential; ignore stale saved metadata.
  const baseProperties: NodeProperty[] =
    nodeType === "OpenAIChat" || nodeType === "openai_gpt" || nodeType === "OpenAICompatible" || nodeType === "openai_compatible"
      ? rawProperties.filter((property: NodeProperty) => property.name !== "model_name")
      : rawProperties;
  // Credentials belong at the start of Basic, regardless of their metadata order.
  const properties = baseProperties
    .map((property) => property.type === "credential-select" ? { ...property, tabName: "basic" } : property)
    .sort((left, right) => Number(right.type === "credential-select") - Number(left.type === "credential-select"));
  const columnMapperSessionsRef = useRef<Record<string, any>>({});

  const tabs = properties.reduce((acc: any[], property: NodeProperty) => {
    const tabId = property.tabName || "basic";
    if (tabId && !acc.find((t) => t.id === tabId)) {
      acc.push({
        id: tabId,
        label: tabId.charAt(0).toUpperCase() + tabId.slice(1),
        icon: Settings,
        description: property.description,
      });
    }
    return acc;
  }, []);

  const [activeTab, setActiveTab] = useState(tabs[0]?.id || "basic");

  // Initialize visibleOptionalFields from previously saved _active_optional_fields
  const [visibleOptionalFields, setVisibleOptionalFields] = useState<Set<string>>(() => {
    const saved = configData?._active_optional_fields;
    return new Set(Array.isArray(saved) ? saved : []);
  });

  const [optionDropdownOpen, setOptionDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOptionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Default values for missing fields
  const initialValues = { ...(propInitialValues || {
    ...properties.reduce((acc: any, property: NodeProperty) => {
      acc[property.name] =
        property.default ?? (property.type === "checkbox" ? false : "");
      return acc;
    }, {}),
    ...configData,
  }) };
  // Older forms copied a credential secret into this undeclared node field.
  if (!properties.some((property) => property.name === "tavily_api_key")) {
    delete initialValues.tavily_api_key;
  }
  if (nodeType === "McpClient" || nodeType === "McpClientTool") {
    delete initialValues.authentication;
  }

  // Validation function
  const validate =
    propValidate ||
    ((values: any) => {
      const errors: any = {};

      return errors;
    });

  // Use the provided onSubmit or fallback to onSave
  const rawSubmit = propOnSubmit || onSave || (() => { });

  const handleSubmit = (values: any) => {
    // Filter out optional fields that were not explicitly added by the user
    const optionalFieldNames = properties
      .filter((p: NodeProperty) => p.type !== "credential-select" && !p.required && !(p.displayOptions?.show))
      .map((p: NodeProperty) => p.name);

    const filteredValues = { ...values };
    if (nodeType === "McpClient" || nodeType === "McpClientTool") {
      delete filteredValues.authentication;
    }
    for (const fieldName of optionalFieldNames) {
      if (!visibleOptionalFields.has(fieldName)) {
        delete filteredValues[fieldName];
      }
    }

    // Store which optional fields are active so the backend knows what to include
    filteredValues._active_optional_fields = Array.from(visibleOptionalFields);

    rawSubmit(filteredValues);
  };

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
  };

  const addOptionalField = (fieldName: string) => {
    setVisibleOptionalFields(prev => new Set(prev).add(fieldName));
  };

  const removeOptionalField = (fieldName: string) => {
    setVisibleOptionalFields(prev => {
      const newSet = new Set(prev);
      newSet.delete(fieldName);
      return newSet;
    });
  };

  const getVisibleProperties = (tabName: string) => {
    return properties
      .filter((property: NodeProperty) => (property.tabName || "basic") === tabName)
      .filter((property: NodeProperty) =>
        property.type === "credential-select" ||
        property.required ||
        visibleOptionalFields.has(property.name) ||
        (property.displayOptions && property.displayOptions.show)
      );
  };

  const getHiddenOptionalProperties = (tabName: string) => {
    return properties
      .filter((property: NodeProperty) => (property.tabName || "basic") === tabName)
      .filter((property: NodeProperty) =>
        property.type !== "credential-select" &&
        !property.required &&
        !visibleOptionalFields.has(property.name) &&
        (!property.displayOptions || !property.displayOptions.show)
      )
  };

  return (
    <div className="w-full h-full">
      {/* Tab Navigation */}
      {tabs.length > 1 && (
        <TabNavigation
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={handleTabChange}
          className="mb-4"
        />
      )}
      <Formik
        initialValues={initialValues}
        validate={validate}
        onSubmit={handleSubmit}
        enableReinitialize
      >
        {({ values, errors, touched, isSubmitting, setFieldValue }) => (
          <>
            <FormValuesObserver values={values} initialValues={initialValues} onChange={onChange} />
            <Form className="grid w-full grid-cols-2 gap-3 p-3">
              {getVisibleProperties(activeTab).map((property: NodeProperty) => {
                // Check display options
                if (property.displayOptions?.show) {
                  const shouldShow = Object.entries(property.displayOptions.show).every(
                    ([key, value]) => {
                      const matches = (name: string, expected: any) => {
                        const current = values[name];
                        // "*" means the field only has to be filled in.
                        if (expected === "*") {
                          return current !== undefined && current !== null && current !== "";
                        }
                        return Array.isArray(expected)
                          ? expected.includes(current)
                          : current === expected;
                      };

                      // "_any" holds alternatives; matching one of them is enough.
                      if (key === "_any" && value && typeof value === "object") {
                        return Object.entries(value).some(([name, expected]) =>
                          matches(name, expected)
                        );
                      }
                      return matches(key, value);
                    }
                  );
                  if (!shouldShow) return null;
                }

                // Visibility is resolved once above. Several field components also
                // contain legacy displayOptions checks that only understand scalar
                // values; passing an already-matched array condition to them can
                // make the input disappear while its outer card remains visible.
                const fullWidthProperty = {
                  ...property,
                  colSpan: 2,
                  displayOptions: undefined,
                };
                const fieldComponent = (() => {
                  switch (property.type) {
                    case "textarea":
                      return <NodeTextArea property={fullWidthProperty} values={values} />;
                    case "readonly-text":
                      return (
                        <NodeReadonlyText
                          property={fullWidthProperty}
                          values={values}
                          setFieldValue={setFieldValue}
                        />
                      );
                    case "select":
                      return <NodeSelect property={fullWidthProperty} values={values} />;
                    case "model-select":
                      return <NodeModelSelect property={fullWidthProperty} values={values} />;
                    case "dynamic-select":
                      return (
                        <NodeDynamicSelect
                          property={fullWidthProperty}
                          values={values}
                          nodeType={nodeType}
                        />
                      );
                    case "column-mapper":
                      return (
                        <NodeColumnMapper
                          property={fullWidthProperty}
                          values={values}
                          nodeType={nodeType}
                          sessionStore={columnMapperSessionsRef.current}
                        />
                      );
                    case "document-editor":
                      return (
                        <NodeDocumentEditor
                          property={fullWidthProperty}
                          values={values}
                          nodeType={nodeType}
                        />
                      );
                    case "mcp-parameters":
                      return <NodeMcpParameters property={fullWidthProperty} values={values} nodeType={nodeType} />;
                    case "credential-select":
                      return (
                        <NodeCredentialSelect
                          property={fullWidthProperty}
                          values={values}
                          setFieldValue={setFieldValue}
                        />
                      );
                    case "text":
                      return <NodeText property={fullWidthProperty} values={values} />;
                    case "number":
                      return <NodeNumber property={fullWidthProperty} values={values} />;
                    case "password":
                      return <NodePassword property={fullWidthProperty} values={values} />;
                    case "checkbox":
                      return <NodeCheckbox property={fullWidthProperty} values={values} />;
                    case "title":
                      return <NodeTitle property={fullWidthProperty} />;
                    case "range":
                      return <NodeRange property={fullWidthProperty} values={values} />;
                    case "json-editor":
                      return (
                        <NodeJsonEditor
                          property={fullWidthProperty}
                          values={values}
                          setFieldValue={setFieldValue}
                        />
                      );
                    case "datetime":
                      return <NodeDateTime property={fullWidthProperty} values={values} />;
                    case "code-editor":
                      return <NodeCodeEditor property={fullWidthProperty} values={values} />;
                    case "session-id":
                      return (
                        <NodeSessionId
                          property={fullWidthProperty}
                          values={values}
                          nodeId={nodeId}
                        />
                      );
                    case "model-artifact-source":
                      return (
                        <NodeModelArtifactSource
                          property={fullWidthProperty}
                          values={values}
                          setFieldValue={setFieldValue}
                          nodeId={nodeId}
                        />
                      );
                    default:
                      return null;
                  }
                })();

                if (!property.required && visibleOptionalFields.has(property.name)) {
                  // Checkbox için kompakt görünüm
                  if (property.type === "checkbox") {
                    return (
                      <div key={property.name} className="kai-node-optional-card kai-node-optional-card--compact">
                        <FieldLabel
                          label={property.displayName}
                          helpText={getFieldHelpText(property)}
                          className="mb-0 min-w-0 text-sm text-[var(--kai-text-soft)]"
                        />
                        <div className="kai-node-optional-actions">
                          {/* Toggle Switch */}
                          <button
                            type="button"
                            onClick={() => setFieldValue(property.name, !values[property.name])}
                            className={`kai-node-toggle ${values[property.name] ? "is-active" : ""}`}
                            role="switch"
                            aria-checked={Boolean(values[property.name])}
                          >
                            <span
                              className="kai-node-toggle-thumb"
                            />
                          </button>
                          {/* Remove Button */}
                          <button
                            type="button"
                            onClick={() => {
                              removeOptionalField(property.name);
                              setFieldValue(property.name, false);
                            }}
                            className="kai-node-optional-remove"
                            aria-label={`Remove ${property.displayName}`}
                            title={`Remove ${property.displayName}`}
                          >
                            <X size={16} />
                          </button>
                        </div>
                      </div>
                    );
                  }

                  // Compact view for Numbers (like a checkbox)
                  if (property.type === "number" && !property.unit) {
                    return (
                      <div key={property.name} className="kai-node-optional-card kai-node-optional-card--compact">
                        <FieldLabel
                          label={property.displayName}
                          helpText={getFieldHelpText(property)}
                          className="mb-0 min-w-0 text-sm text-[var(--kai-text-soft)]"
                        />
                        <div className="kai-node-optional-actions">
                          <ThemedNumberInput
                            value={values[property.name] ?? property.default ?? ""}
                            onChange={(nextValue) =>
                              setFieldValue(
                                property.name,
                                nextValue === "" ? "" : Number(nextValue)
                              )
                            }
                            min={property.min}
                            max={property.max}
                            step={property.step}
                            ariaLabel={property.displayName}
                            size="compact"
                            className="w-28"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              removeOptionalField(property.name);
                              setFieldValue(property.name, property.default ?? "");
                            }}
                            className="kai-node-optional-remove"
                            aria-label={`Remove ${property.displayName}`}
                            title={`Remove ${property.displayName}`}
                          >
                            <X size={16} />
                          </button>
                        </div>
                      </div>
                    );
                  }

                  // Diğer field türleri için container stili
                  return (
                    <div key={property.name} className="kai-node-optional-card kai-node-optional-card--with-action-rail">
                      {fieldComponent}
                      <button
                        type="button"
                        onClick={() => removeOptionalField(property.name)}
                        className="kai-node-optional-remove kai-node-optional-remove--rail"
                        aria-label={`Remove ${property.displayName}`}
                        title={`Remove ${property.displayName}`}
                      >
                        <X size={16} />
                      </button>
                    </div>
                  );
                }

                return (
                  <div
                    key={property.name}
                    className={
                      property.type === "title"
                        ? "col-span-2 pt-3 pb-1"
                        : "col-span-2 rounded-lg border border-[var(--kai-navigation-border)] bg-[var(--kai-overlay-surface)] px-4 py-3"
                    }
                  >
                    {fieldComponent}
                  </div>
                );
              })}

              {/* Add Option Dropdown */}
              {getHiddenOptionalProperties(activeTab).length > 0 && (
                <div className="col-span-2 mt-3 border-t border-[var(--kai-navigation-border)] pt-4">
                  <div className="relative" ref={dropdownRef}>
                    <button
                      type="button"
                      onClick={() => setOptionDropdownOpen(!optionDropdownOpen)}
                      className="group flex w-full cursor-pointer items-center justify-between rounded-lg border border-dashed border-[var(--kai-config-dashed-border)] bg-[var(--kai-surface-selected)] px-4 py-2.5 text-[var(--kai-text-secondary)] transition-colors hover:border-[var(--kai-config-dashed-border-hover)] hover:bg-[var(--kai-border-dialog)] hover:text-[var(--kai-text)]"
                    >
                      <span className="flex items-center gap-2 text-sm font-medium">
                        <Plus size={16} className="text-[var(--kai-text-muted)] transition-colors group-hover:text-[var(--kai-text)]" />
                        Add Option
                      </span>
                      <ChevronDown
                        size={16}
                        className={`text-[var(--kai-text-muted)] transition-all duration-200 group-hover:text-[var(--kai-text)] ${optionDropdownOpen ? "rotate-180" : ""}`}
                      />
                    </button>

                    {optionDropdownOpen && (
                      <div className="kai-node-field-menu absolute left-0 right-0 z-50 mt-1">
                        {getHiddenOptionalProperties(activeTab).map((property: NodeProperty) => (
                          <button
                            key={property.name}
                            type="button"
                            onClick={() => {
                              addOptionalField(property.name);
                              setOptionDropdownOpen(false);
                            }}
                            className="group flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm text-[var(--kai-text-secondary)] transition-colors duration-150 hover:bg-[var(--kai-config-menu-hover-bg)] hover:text-[var(--kai-text)]"
                          >
                            <Plus size={14} className="flex-shrink-0 text-[var(--kai-text-muted)] group-hover:text-[var(--kai-text-secondary)]" />
                            {property.displayName}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Form>
          </>
        )}
      </Formik>
    </div>
  );
}
