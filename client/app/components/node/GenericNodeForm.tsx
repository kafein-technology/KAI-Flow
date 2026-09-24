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
  const rawProperties = configData?.metadata?.properties || [];
  const nodeType =
    configData?.metadata?.name || configData?.name || configData?.type;
  // OpenAI GPT and OpenAI Compatible take the model from the credential; ignore stale saved metadata.
  const properties =
    nodeType === "OpenAIChat" || nodeType === "openai_gpt" || nodeType === "OpenAICompatible" || nodeType === "openai_compatible"
      ? rawProperties.filter((property: NodeProperty) => property.name !== "model_name")
      : rawProperties;
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
  const initialValues = propInitialValues || {
    ...properties.reduce((acc: any, property: NodeProperty) => {
      acc[property.name] =
        property.default ?? (property.type === "checkbox" ? false : "");
      return acc;
    }, {}),
    ...configData,
  };

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
      .filter((p: NodeProperty) => !p.required && !(p.displayOptions?.show))
      .map((p: NodeProperty) => p.name);

    const filteredValues = { ...values };
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
        property.required ||
        visibleOptionalFields.has(property.name) ||
        (property.displayOptions && property.displayOptions.show)
      );
  };

  const getHiddenOptionalProperties = (tabName: string) => {
    return properties
      .filter((property: NodeProperty) => (property.tabName || "basic") === tabName)
      .filter((property: NodeProperty) =>
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
            <Form className="grid grid-cols-2 gap-3 w-full p-6">
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
                          setFieldValue={setFieldValue}
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
                      <div key={property.name} className="col-span-2 flex items-center justify-between bg-slate-800/50 border border-slate-600 rounded-lg px-4 py-3">
                        <FieldLabel
                          label={property.displayName}
                          helpText={getFieldHelpText(property)}
                          className="text-sm text-slate-200"
                        />
                        <div className="flex items-center gap-3">
                          {/* Toggle Switch */}
                          <button
                            type="button"
                            onClick={() => setFieldValue(property.name, !values[property.name])}
                            className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${values[property.name] ? "bg-blue-500" : "bg-slate-600"
                              }`}
                          >
                            <span
                              className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform duration-200 ${values[property.name] ? "translate-x-5" : "translate-x-0"
                                }`}
                            />
                          </button>
                          {/* Remove Button */}
                          <button
                            type="button"
                            onClick={() => {
                              removeOptionalField(property.name);
                              setFieldValue(property.name, false);
                            }}
                            className="text-slate-400 hover:text-red-400 transition-colors"
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
                      <div key={property.name} className="col-span-2 flex items-center justify-between bg-slate-800/50 border border-slate-600 rounded-lg px-4 py-3">
                        <FieldLabel
                          label={property.displayName}
                          helpText={getFieldHelpText(property)}
                          className="text-sm text-slate-200"
                        />
                        <div className="flex items-center gap-3">
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
                            className="text-slate-400 hover:text-red-400 transition-colors"
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
                    <div key={property.name} className="col-span-2 relative bg-slate-800/50 border border-slate-600 rounded-lg px-4 py-3">
                      {fieldComponent}
                      <button
                        type="button"
                        onClick={() => removeOptionalField(property.name)}
                        className="absolute top-3 right-4 text-slate-400 hover:text-red-400 transition-colors"
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
                        : "col-span-2 bg-slate-800/50 border border-slate-600 rounded-lg px-4 py-3"
                    }
                  >
                    {fieldComponent}
                  </div>
                );
              })}

              {/* Add Option Dropdown */}
              {getHiddenOptionalProperties(activeTab).length > 0 && (
                <div className="col-span-2 mt-4 border-t border-slate-600 pt-4">
                  <div className="relative" ref={dropdownRef}>
                    <button
                      type="button"
                      onClick={() => setOptionDropdownOpen(!optionDropdownOpen)}
                      className="w-full flex items-center justify-between bg-slate-700/50 border border-dashed border-slate-500 rounded-lg px-4 py-2.5 text-slate-300 cursor-pointer hover:bg-slate-600/50 hover:border-slate-400 hover:text-white transition-all duration-200 group"
                    >
                      <span className="flex items-center gap-2 text-sm font-medium">
                        <Plus size={16} className="text-slate-400 group-hover:text-blue-400 transition-colors duration-200" />
                        Add Option
                      </span>
                      <ChevronDown
                        size={16}
                        className={`text-slate-400 group-hover:text-white transition-all duration-200 ${optionDropdownOpen ? "rotate-180" : ""}`}
                      />
                    </button>

                    {optionDropdownOpen && (
                      <div className="absolute z-50 mt-1 left-0 right-0 bg-slate-900 border border-slate-700 rounded-lg shadow-lg shadow-black/40 overflow-hidden">
                        {getHiddenOptionalProperties(activeTab).map((property: NodeProperty) => (
                          <button
                            key={property.name}
                            type="button"
                            onClick={() => {
                              addOptionalField(property.name);
                              setOptionDropdownOpen(false);
                            }}
                            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-slate-300 hover:bg-blue-500/20 hover:text-blue-300 transition-colors duration-150 text-left group"
                          >
                            <Plus size={14} className="text-slate-500 group-hover:text-blue-300 flex-shrink-0" />
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
