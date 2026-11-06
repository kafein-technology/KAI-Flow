import { Plus, Trash2 } from "lucide-react";
import type { NodeProperty } from "../types";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

type Choice = { name: string; description: string };

interface Props {
  property: NodeProperty;
  value: unknown;
  setValue: (name: string, value: Choice[] | string[]) => void;
}

const inputClass = "kai-node-field-control min-w-0 px-3 py-2 text-sm";

export function NodeDecisionCriteria({ property, value, setValue }: Props) {
  const isChoice = property.name === "choice_criteria";
  const limit = isChoice ? 255 : 10;
  const rows = Array.isArray(value) ? value : Array.isArray(property.default) ? property.default : [];
  const update = (next: Choice[] | string[]) => setValue(property.name, next);

  return (
    <div className="col-span-2 space-y-3">
      <FieldLabel label={property.displayName} helpText={getFieldHelpText(property)} />
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div key={index} className="rounded-xl border border-[var(--kai-border-soft)] bg-[var(--kai-surface-control)] p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-[var(--kai-text-muted)]">
                {isChoice ? `Choice ${index + 1}` : `Score ${index}`}
              </span>
              <button
                type="button"
                className="rounded-md p-1.5 text-[var(--kai-text-muted)] hover:bg-[var(--kai-border-soft)] hover:text-[var(--kai-text)] disabled:opacity-40"
                aria-label={`Remove ${isChoice ? "choice" : "score level"} ${index + 1}`}
                disabled={rows.length <= (isChoice ? 1 : 2)}
                onClick={() => update(rows.filter((_, rowIndex) => rowIndex !== index))}
              >
                <Trash2 size={15} />
              </button>
            </div>
            {isChoice ? (
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
                <input
                  className={inputClass}
                  value={typeof row === "object" && row ? (row as Choice).name ?? "" : ""}
                  maxLength={255}
                  placeholder="Name, e.g. urgent"
                  aria-label={`Choice ${index + 1} name`}
                  onChange={(event) => update(rows.map((item, rowIndex) => rowIndex === index ? { ...(item as Choice), name: event.target.value } : item) as Choice[])}
                />
                <input
                  className={inputClass}
                  value={typeof row === "object" && row ? (row as Choice).description ?? "" : ""}
                  maxLength={255}
                  placeholder="When this choice applies (optional)"
                  aria-label={`Choice ${index + 1} description`}
                  onChange={(event) => update(rows.map((item, rowIndex) => rowIndex === index ? { ...(item as Choice), description: event.target.value } : item) as Choice[])}
                />
              </div>
            ) : (
              <input
                className={`${inputClass} w-full`}
                value={typeof row === "string" ? row : ""}
                placeholder={index === 0 ? "Lowest level" : "Describe this level"}
                aria-label={`Score level ${index} description`}
                onChange={(event) => update(rows.map((item, rowIndex) => rowIndex === index ? event.target.value : item) as string[])}
              />
            )}
          </div>
        ))}
      </div>
      <button
        type="button"
        disabled={rows.length >= limit}
        onClick={() => update([...rows, isChoice ? { name: "", description: "" } : ""] as Choice[] | string[])}
        className="flex items-center gap-2 rounded-lg border border-[var(--kai-control-border)] px-3 py-2 text-sm text-[var(--kai-text-soft)] hover:border-[var(--kai-accent)] hover:text-[var(--kai-text)] disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Plus size={16} /> Add {isChoice ? "choice" : "score level"}
      </button>
    </div>
  );
}
