import React from "react";
import { XIcon as X, SaveIcon as Save, FileTextIcon as FileText, GlobeIcon as Globe, LockIcon as Lock, PencilIcon as Pencil } from "../../icons/index";
import { Formik, Form, Field, ErrorMessage } from "formik";

interface WorkflowFormValues {
  name: string;
  description: string;
  is_public: boolean;
}

interface Workflow {
  id: string;
  name: string;
  description?: string;
  is_public: boolean;
  flow_data?: any;
}

interface WorkflowEditModalProps {
  isOpen: boolean;
  workflow: Workflow | null;
  onClose: () => void;
  onSubmit: (values: WorkflowFormValues) => Promise<void>;
  isLoading?: boolean;
}

const validateWorkflow = (values: WorkflowFormValues) => {
  const errors: Partial<WorkflowFormValues> = {};
  
  if (!values.name.trim()) {
    errors.name = "Workflow name is required";
  } else if (values.name.trim().length < 3) {
    errors.name = "Workflow name must be at least 3 characters";
  } else if (values.name.trim().length > 50) {
    errors.name = "Workflow name must be less than 50 characters";
  }
  
  if (values.description && values.description.length > 200) {
    errors.description = "Description must be less than 200 characters";
  }
  
  return errors;
};

export default function WorkflowEditModal({
  isOpen,
  workflow,
  onClose,
  onSubmit,
  isLoading = false
}: WorkflowEditModalProps) {
  if (!isOpen || !workflow) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 backdrop-blur-sm z-50 transition-all duration-300"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 bg-purple-100 rounded-xl">
                <Pencil className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Edit Workflow</h3>
                <p className="text-sm text-gray-500">Update workflow details</p>
              </div>
            </div>
            <button
              onClick={onClose}
              disabled={isLoading}
              className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            <Formik
              enableReinitialize
              initialValues={{
                name: workflow.name || "",
                description: workflow.description || "",
                is_public: workflow.is_public || false,
              }}
              validate={validateWorkflow}
              onSubmit={async (values, { setSubmitting }) => {
                try {
                  await onSubmit(values);
                  onClose();
                } catch (error) {
                  console.error('Failed to update workflow:', error);
                } finally {
                  setSubmitting(false);
                }
              }}
            >
              {({ isSubmitting, values }) => (
                <Form className="space-y-6">
                  {/* Name Field */}
                  <div>
                    <label htmlFor="name" className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                      <FileText className="w-4 h-4" />
                      Workflow Name
                    </label>
                    <Field
                      name="name"
                      type="text"
                      placeholder="Enter workflow name"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 text-sm"
                    />
                    <ErrorMessage
                      name="name"
                      component="p"
                      className="mt-1 text-xs text-red-600"
                    />
                  </div>

                  {/* Description Field */}
                  <div>
                    <label htmlFor="description" className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                      <FileText className="w-4 h-4" />
                      Description
                      <span className="text-xs text-gray-500">(optional)</span>
                    </label>
                    <Field
                      name="description"
                      as="textarea"
                      rows={3}
                      placeholder="Enter workflow description"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200 text-sm resize-none"
                    />
                    <div className="mt-1 flex justify-between">
                      <ErrorMessage
                        name="description"
                        component="p"
                        className="text-xs text-red-600"
                      />
                      <span className="text-xs text-gray-500">
                        {values.description.length}/200
                      </span>
                    </div>
                  </div>

                  {/* Public Toggle */}
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-8 h-8 bg-white rounded-lg border border-gray-200">
                        {values.is_public ? (
                          <Globe className="w-4 h-4 text-green-600" />
                        ) : (
                          <Lock className="w-4 h-4 text-gray-600" />
                        )}
                      </div>
                      <div>
                        <label htmlFor="is_public" className="text-sm font-medium text-gray-700">
                          {values.is_public ? 'Public Workflow' : 'Private Workflow'}
                        </label>
                        <p className="text-xs text-gray-500">
                          {values.is_public 
                            ? 'Anyone can view and use this workflow' 
                            : 'Only you can access this workflow'
                          }
                        </p>
                      </div>
                    </div>
                    <Field name="is_public">
                      {({ field }: any) => (
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            className="sr-only peer"
                            {...field}
                            checked={field.value}
                          />
                          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
                        </label>
                      )}
                    </Field>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
                    <button
                      type="button"
                      onClick={onClose}
                      disabled={isSubmitting}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting || isLoading}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                    >
                      {isSubmitting ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Save className="w-4 h-4" />
                          Save Changes
                        </>
                      )}
                    </button>
                  </div>
                </Form>
              )}
            </Formik>
          </div>
        </div>
      </div>
    </>
  );
}