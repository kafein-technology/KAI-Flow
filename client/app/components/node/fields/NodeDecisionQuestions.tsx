import { ErrorMessage, useFormikContext } from "formik";
import { Plus, Trash2 } from "lucide-react";
import type { NodeProperty } from "../types";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";
import { VariableAutocompleteField } from "./VariableAutocompleteField";

interface NoulQuestion {
  id: string;
  instructions: string;
  true_criterion?: string;
  false_criterion?: string;
}

export function NodeDecisionQuestions({ property }: { property: NodeProperty }) {
  const { values, setValues } = useFormikContext<Record<string, any>>();
  const additional: NoulQuestion[] = Array.isArray(values[property.name]) ? values[property.name] : [];
  // Keep the original fields for the first question so saved workflows retain
  // their input-envelope behavior and their existing output.value references.
  const questions: NoulQuestion[] = [{
    id: "decision",
    instructions: values.instructions ?? "",
    true_criterion: values.true_criterion ?? "",
    false_criterion: values.false_criterion ?? "",
  }, ...additional];

  const addQuestion = () => {
    let number = 2;
    while (questions.some((question) => question.id === `decision_${number}`)) number += 1;
    void setValues({
      ...values,
      [property.name]: [...additional, { id: `decision_${number}`, instructions: "", true_criterion: "", false_criterion: "" }],
    });
  };

  const removeQuestion = (index: number) => {
    if (questions.length === 1) return;
    if (index === 0) {
      const [first, ...remaining] = additional;
      void setValues({
        ...values,
        instructions: first.instructions,
        true_criterion: first.true_criterion ?? "",
        false_criterion: first.false_criterion ?? "",
        [property.name]: remaining,
      });
    } else {
      void setValues({ ...values, [property.name]: additional.filter((_, rowIndex) => rowIndex !== index - 1) });
    }
  };

  return (
    <div className="col-span-2 space-y-3">
      <FieldLabel label={property.displayName} helpText={getFieldHelpText(property)} />
      <div className="space-y-3">
        {questions.map((question, index) => {
          const prefix = index === 0 ? "" : `${property.name}[${index - 1}].`;
          return (
            <fieldset key={question.id} className="min-w-0 space-y-3 rounded-lg border border-[var(--kai-border-soft)] bg-[var(--kai-surface-control)] p-3">
              <legend className="sr-only">Noul question {index + 1}</legend>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-[var(--kai-text-soft)]">Question {index + 1}</span>
                <button
                  type="button"
                  aria-label={`Remove Noul question ${index + 1}`}
                  disabled={questions.length === 1}
                  onClick={() => removeQuestion(index)}
                  className="rounded-md p-1.5 text-[var(--kai-text-muted)] hover:bg-[var(--kai-border-soft)] hover:text-[var(--kai-text)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--kai-accent)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Trash2 size={15} />
                </button>
              </div>
              <label className="block space-y-1.5 text-sm text-[var(--kai-text-soft)]">
                <span>Instructions</span>
                <VariableAutocompleteField
                  as="textarea"
                  name={`${prefix}instructions`}
                  rows={3}
                  placeholder="Is this message about billing?"
                  className="kai-node-field-control w-full resize-y px-3 py-2 text-sm"
                />
              </label>
              <ErrorMessage name={`${prefix}instructions`} component="div" className="kai-node-field-error" />
              <div className="grid gap-3 sm:grid-cols-2">
                {([ ["true_criterion", "Yes / true means"], ["false_criterion", "No / false means"] ] as const).map(([name, label]) => (
                  <label key={name} className="block min-w-0 space-y-1.5 text-sm text-[var(--kai-text-soft)]">
                    <span>{label}</span>
                    <VariableAutocompleteField
                      as="textarea"
                      name={`${prefix}${name}`}
                      rows={2}
                      placeholder="Optional clarification"
                      className="kai-node-field-control w-full resize-y px-3 py-2 text-sm"
                    />
                  </label>
                ))}
              </div>
              {questions.length > 1 && <p className="text-xs text-[var(--kai-text-muted)]">Result: decisions.{question.id}</p>}
            </fieldset>
          );
        })}
      </div>
      <button
        type="button"
        onClick={addQuestion}
        className="flex items-center gap-2 rounded-lg border border-[var(--kai-control-border)] px-3 py-2 text-sm text-[var(--kai-text-soft)] hover:border-[var(--kai-accent)] hover:text-[var(--kai-text)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--kai-accent)]"
      >
        <Plus size={16} /> Add Noul question
      </button>
    </div>
  );
}
