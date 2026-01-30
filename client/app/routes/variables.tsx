import { Formik, Form, Field, ErrorMessage } from "formik";
import { enqueueSnackbar, useSnackbar } from "notistack";
import React, { useEffect, useState } from "react";
import {
  Search,
  Plus,
  Pencil,
  Trash,
  ChevronLeft,
  ChevronRight,
  X,
  Save,
  Edit,
} from "~/components/common/Icon";
import AuthGuard from "~/components/AuthGuard";
import DashboardSidebar from "~/components/dashboard/DashboardSidebar";
import { useVariableStore } from "~/stores/variables";
import { timeAgo } from "~/lib/dateFormatter";
import Loading from "~/components/Loading";

interface VariableFormValues {
  name: string;
  type: string;
  value: string;
}

function VariablesLayout() {
  const { enqueueSnackbar } = useSnackbar();
  const [searchQuery, setSearchQuery] = useState("");
  const [editingVariable, setEditingVariable] = useState<any>(null);
  const [itemsPerPage, setItemsPerPage] = useState(6);
  const [page, setPage] = useState(1);

  const {
    variables,
    fetchVariables,
    isLoading,
    removeVariable: removeVariableFromStore,
    updateVariable,
    createVariable,
  } = useVariableStore();

  useEffect(() => {
    fetchVariables();
  }, [fetchVariables]);

  const handleVariableSubmit = async (
    values: VariableFormValues,
    { resetForm }: any
  ) => {
    try {
      await createVariable(values);
      enqueueSnackbar("Variable created successfully", { variant: "success" });
      const modal = document.getElementById(
        "modalCreateVariable"
      ) as HTMLDialogElement;
      modal?.close();
      resetForm();
    } catch (error: any) {
      enqueueSnackbar(error.message || "Failed to create variable", {
        variant: "error",
      });
    }
  };

  const handleVariableUpdate = async (
    values: VariableFormValues,
    { resetForm }: any
  ) => {
    try {
      if (editingVariable) {
        await updateVariable(editingVariable.id, values);
        enqueueSnackbar("Variable updated successfully", {
          variant: "success",
        });
        const modal = document.getElementById(
          "modalUpdateVariable"
        ) as HTMLDialogElement;
        modal?.close();
        setEditingVariable(null);
        resetForm();
      }
    } catch (error: any) {
      enqueueSnackbar(error.message || "Failed to update variable", {
        variant: "error",
      });
    }
  };

  const handleEditClick = (variable: any) => {
    setEditingVariable(variable);
    const modal = document.getElementById(
      "modalUpdateVariable"
    ) as HTMLDialogElement;
    modal?.showModal();
  };

  const validateVariable = (values: VariableFormValues) => {
    const errors: Partial<VariableFormValues> = {};
    if (!values.name) {
      errors.name = "Variable name is required";
    } else if (values.name.length < 2) {
      errors.name = "Must be at least 2 characters";
    } else if (!/^[A-Z][A-Z0-9_]*$/i.test(values.name)) {
      errors.name = "Only letters, numbers, and underscores allowed";
    }
    if (!values.value) errors.value = "Value is required";
    if (!values.type) errors.type = "Type is required";
    return errors;
  };

  const handleDelete = async (id: string) => {
    try {
      await removeVariableFromStore(id);
      enqueueSnackbar("Variable deleted", { variant: "success" });
    } catch (error: any) {
      enqueueSnackbar(error.message || "Failed to delete", {
        variant: "error",
      });
    }
  };

  const filteredVariables = variables.filter(
    (v) =>
      v.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.value.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalItems = filteredVariables.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));
  const startIdx = (page - 1) * itemsPerPage;
  const endIdx = Math.min(startIdx + itemsPerPage, totalItems);
  const pagedVariables = filteredVariables.slice(startIdx, endIdx);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [totalPages, page]);

  return (
    <div className="flex h-screen bg-background text-foreground">
      <DashboardSidebar />
      <main className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
              <div>
                <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                  Variables
                </h1>
                <p className="text-gray-600 text-lg">
                  Manage your application variables and configuration values
                </p>
              </div>
              <div className="flex items-center gap-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="search"
                    className="pl-10 pr-4 py-2 w-64 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200"
                    placeholder="Search variables..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <button
                  className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl hover:from-purple-700 hover:to-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl"
                  onClick={() =>
                    (
                      document.getElementById(
                        "modalCreateVariable"
                      ) as HTMLDialogElement
                    )?.showModal()
                  }
                >
                  <Plus className="w-5 h-5" />
                  Create Variable
                </button>
              </div>
            </div>

            {/* Content */}
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loading size="sm" />
              </div>
            ) : pagedVariables.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-6 py-12">
                <div className="text-center">
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    No variables found
                  </h3>
                  <p className="text-gray-600">
                    Create your first variable to get started.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {pagedVariables.map((variable) => (
                  <div
                    key={variable.id}
                    className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-md transition-all duration-200"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex-1">
                          <h3 className="text-lg font-semibold text-gray-900 font-mono">
                            {variable.name}
                          </h3>
                          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                            <span>Created: {timeAgo(variable.created_at)}</span>
                            <span>Updated: {timeAgo(variable.updated_at)}</span>
                            <span className="text-xs text-gray-400 font-mono">
                              ID: {variable.id.slice(0, 8)}...
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <span
                          className={`inline-flex px-3 py-1 text-xs font-semibold rounded-full border ${
                            variable.type === "static"
                              ? "bg-blue-100 text-blue-800 border-blue-200"
                              : "bg-green-100 text-green-800 border-green-200"
                          }`}
                        >
                          {variable.type}
                        </span>

                        <div className="flex items-center gap-1">
                          <button
                            title="Edit variable"
                            className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all duration-200"
                            onClick={() => handleEditClick(variable)}
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            title="Delete variable"
                            className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200"
                            onClick={() => handleDelete(variable.id)}
                          >
                            <Trash className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Value Display */}
                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <p className="text-gray-600 text-sm font-mono break-all">
                        {variable.value}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Pagination */}
        {!isLoading && pagedVariables.length > 0 && (
          <div className="mt-8">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-white border border-gray-200 rounded-2xl shadow-sm">
              {/* Items per page */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">Items per page:</span>
                <select
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white text-gray-900 focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200"
                  value={itemsPerPage}
                  onChange={(e) => {
                    setItemsPerPage(Number(e.target.value));
                    setPage(1);
                  }}
                >
                  {[6, 10, 20, 50, 100].map((opt) => (
                    <option
                      key={opt}
                      value={opt}
                      className="bg-white text-gray-900"
                    >
                      {opt}
                    </option>
                  ))}
                </select>
              </div>

              {/* Sayfa numaraları */}
              <div className="flex items-center gap-2 justify-center">
                <button
                  className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>

                {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                  (p) => (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all duration-200 ${
                        p === page
                          ? "bg-gradient-to-r from-purple-600 to-blue-600 text-white border-transparent shadow-lg"
                          : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400"
                      }`}
                    >
                      {p}
                    </button>
                  )
                )}

                <button
                  className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={() => setPage(page + 1)}
                  disabled={page === totalPages}
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>

              {/* Items X to Y of Z */}
              <div className="text-sm text-gray-600 text-right">
                Items {totalItems === 0 ? 0 : startIdx + 1} to {endIdx} of{" "}
                {totalItems}
              </div>
            </div>
          </div>
        )}

        {/* Create Variable Modal */}
        <dialog
          id="modalCreateVariable"
          className="modal modal-bottom sm:modal-middle backdrop-blur-sm"
        >
          <div className="modal-box max-w-md bg-white shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Create Variable</h3>
              <button
                className="btn btn-sm btn-circle btn-ghost"
                onClick={() => {
                  const modal = document.getElementById(
                    "modalCreateVariable"
                  ) as HTMLDialogElement;
                  modal?.close();
                }}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <Formik
              initialValues={{
                name: "",
                type: "static",
                value: "",
              }}
              validate={validateVariable}
              onSubmit={handleVariableSubmit}
            >
              {({ isSubmitting }) => (
                <Form className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Variable Name
                    </label>
                    <Field
                      name="name"
                      className="input input-bordered w-full"
                      placeholder="VARIABLE_NAME"
                    />
                    <ErrorMessage
                      name="name"
                      component="div"
                      className="text-red-500 text-sm mt-1"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Type
                    </label>
                    <Field
                      as="select"
                      name="type"
                      className="select select-bordered w-full"
                    >
                      <option value="static">Static</option>
                      <option value="dynamic">Dynamic</option>
                    </Field>
                    <ErrorMessage
                      name="type"
                      component="div"
                      className="text-red-500 text-sm mt-1"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Value
                    </label>
                    <Field
                      as="textarea"
                      name="value"
                      className="textarea textarea-bordered w-full h-24"
                      placeholder="Enter variable value..."
                    />
                    <ErrorMessage
                      name="value"
                      component="div"
                      className="text-red-500 text-sm mt-1"
                    />
                  </div>

                  <div className="flex justify-end gap-2 pt-4">
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={() => {
                        const modal = document.getElementById(
                          "modalCreateVariable"
                        ) as HTMLDialogElement;
                        modal?.close();
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn-primary"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? (
                        <div className="loading loading-spinner loading-sm"></div>
                      ) : (
                        <>
                          <Save className="w-4 h-4" />
                          Create
                        </>
                      )}
                    </button>
                  </div>
                </Form>
              )}
            </Formik>
          </div>
        </dialog>

        {/* Update Variable Modal */}
        <dialog
          id="modalUpdateVariable"
          className="modal modal-bottom sm:modal-middle backdrop-blur-sm"
        >
          <div className="modal-box max-w-md bg-white shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Update Variable</h3>
              <button
                className="btn btn-sm btn-circle btn-ghost"
                onClick={() => {
                  const modal = document.getElementById(
                    "modalUpdateVariable"
                  ) as HTMLDialogElement;
                  modal?.close();
                  setEditingVariable(null);
                }}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {editingVariable && (
              <Formik
                initialValues={{
                  name: editingVariable.name,
                  type: editingVariable.type,
                  value: editingVariable.value,
                }}
                validate={validateVariable}
                onSubmit={handleVariableUpdate}
                enableReinitialize
              >
                {({ isSubmitting }) => (
                  <Form className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Variable Name
                      </label>
                      <Field
                        name="name"
                        className="input input-bordered w-full"
                        placeholder="VARIABLE_NAME"
                      />
                      <ErrorMessage
                        name="name"
                        component="div"
                        className="text-red-500 text-sm mt-1"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Type
                      </label>
                      <Field
                        as="select"
                        name="type"
                        className="select select-bordered w-full"
                      >
                        <option value="static">Static</option>
                        <option value="dynamic">Dynamic</option>
                      </Field>
                      <ErrorMessage
                        name="type"
                        component="div"
                        className="text-red-500 text-sm mt-1"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Value
                      </label>
                      <Field
                        as="textarea"
                        name="value"
                        className="textarea textarea-bordered w-full h-24"
                        placeholder="Enter variable value..."
                      />
                      <ErrorMessage
                        name="value"
                        component="div"
                        className="text-red-500 text-sm mt-1"
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-4">
                      <button
                        type="button"
                        className="btn btn-outline"
                        onClick={() => {
                          const modal = document.getElementById(
                            "modalUpdateVariable"
                          ) as HTMLDialogElement;
                          modal?.close();
                          setEditingVariable(null);
                        }}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? (
                          <div className="loading loading-spinner loading-sm"></div>
                        ) : (
                          <>
                            <Save className="w-4 h-4" />
                            Update
                          </>
                        )}
                      </button>
                    </div>
                  </Form>
                )}
              </Formik>
            )}
          </div>
        </dialog>
      </main>
    </div>
  );
}

export default function ProtectedVariablesLayout() {
  return (
    <AuthGuard>
      <VariablesLayout />
    </AuthGuard>
  );
}
