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
  NodeCheckbox,
  NodeTitle,
  NodeRange,
  NodeJsonEditor,
  NodeDateTime,
  NodeCodeEditor,
} from "./fields";
import TabNavigation from "../common/TabNavigation";
import { useState } from "react";
import { Settings } from "../../icons/index";

interface GenericNodeFormProps {
  initialValues?: GenericData;
  validate?: (values: Partial<GenericData>) => any;
  onSubmit?: (values: GenericData) => void;
  onCancel: () => void;
  configData?: any;
  onSave?: (values: any) => void;
}

export default function GenericNodeForm({
  initialValues: propInitialValues,
  validate: propValidate,
  onSubmit: propOnSubmit,
  onCancel,
  configData,
  onSave,
}: GenericNodeFormProps) {
  const properties = configData?.metadata?.properties || [];

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

  /*
    const initialValues = propInitialValues || {
      ...configData,
      include_answer: configData?.include_answer || false,
      include_raw_content: configData?.include_raw_content || false,
      include_images: configData?.include_images || false,
      rate_limit_requests: configData?.rate_limit_requests || 10,
      rate_limit_window: configData?.rate_limit_window || 60,
      text_input: configData?.text_input || "",
    };
  */

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
  const handleSubmit = propOnSubmit || onSave || (() => { });

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
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
          <Form className="grid grid-cols-2 gap-3 w-full p-6">
            {properties
              .filter(
                (property: NodeProperty) => (property.tabName || "basic") === activeTab
              )
              .map((property: NodeProperty) => {
                switch (property.type) {
                  case "textarea":
                    return <NodeTextArea property={property} values={values} />;
                  case "readonly-text":
                    return (
                      <NodeReadonlyText
                        property={property}
                        values={values}
                        setFieldValue={setFieldValue}
                      />
                    );
                  case "select":
                    return <NodeSelect property={property} values={values} />;
                  case "credential-select":
                    return (
                      <NodeCredentialSelect
                        property={property}
                        values={values}
                        setFieldValue={setFieldValue}
                      />
                    );
                  case "text":
                    return <NodeText property={property} values={values} />;
                  case "number":
                    return <NodeNumber property={property} values={values} />;
                  case "password":
                    return <NodePassword property={property} values={values} />;
                  case "checkbox":
                    return <NodeCheckbox property={property} values={values} />;
                  case "title":
                    return <NodeTitle property={property} />;
                  case "range":
                    return <NodeRange property={property} values={values} />;
                  case "json-editor":
                    return (
                      <NodeJsonEditor
                        property={property}
                        values={values}
                        setFieldValue={setFieldValue}
                      />
                    );
                  case "datetime":
                    return <NodeDateTime property={property} values={values} />;
                  case "code-editor":
                    return <NodeCodeEditor property={property} values={values} />;
                  default:
                    return null;
                }
              })}
          </Form>
        )}
      </Formik>
    </div>
  );
}
