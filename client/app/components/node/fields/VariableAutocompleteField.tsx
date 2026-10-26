import { useField } from "formik";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, CSSProperties, FocusEvent, KeyboardEvent, MouseEvent, TouchEvent, Ref } from "react";
import { createPortal } from "react-dom";
import { useVariableStore } from "~/stores/variables";
import { useWorkflows } from "~/stores/workflows";
import type { Variable } from "~/types/api";
import { findVariableCompletion, resolveVariablePreview, type VariableCompletion } from "./variableCompletion";

type TextControl = HTMLInputElement | HTMLTextAreaElement;

interface VariableAutocompleteFieldProps {
  name: string;
  as?: "input" | "textarea";
  className?: string;
  placeholder?: string;
  rows?: number;
  style?: CSSProperties;
  onMouseDown?: (event: MouseEvent<TextControl>) => void;
  onTouchStart?: (event: TouchEvent<TextControl>) => void;
}

export function VariableAutocompleteField({
  name,
  ...props
}: VariableAutocompleteFieldProps) {
  const [field, , helpers] = useField<string>(name);
  return (
    <VariableAutocompleteControl
      {...props}
      name={name}
      value={String(field.value ?? "")}
      onValueChange={(value) => { void helpers.setValue(value); }}
      onBlur={field.onBlur}
    />
  );
}

interface VariableAutocompleteControlProps extends VariableAutocompleteFieldProps {
  value: string;
  onValueChange: (value: string) => void;
  onBlur?: (event: FocusEvent<TextControl>) => void;
}

export function VariableAutocompleteControl({
  name,
  as = "input",
  className,
  placeholder,
  rows,
  style,
  onMouseDown,
  onTouchStart,
  value,
  onValueChange,
  onBlur,
}: VariableAutocompleteControlProps) {
  const inputRef = useRef<TextControl>(null);
  const optionsRef = useRef<HTMLDivElement>(null);
  const [completion, setCompletion] = useState<VariableCompletion | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isFocused, setIsFocused] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0, width: 280 });
  const variables = useVariableStore((state) => state.variables);
  const workflowId = useWorkflows((state) => state.currentWorkflow?.id);

  const available = useMemo(() => {
    const byName = new Map<string, Variable>();
    for (const variable of variables) {
      if (variable.workflow_id === null) byName.set(variable.name, variable);
    }
    for (const variable of variables) {
      if (workflowId && variable.workflow_id === workflowId) byName.set(variable.name, variable);
    }
    return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [variables, workflowId]);

  const matches = useMemo(
    () => available.filter((variable) => variable.name.toLowerCase().includes(completion?.query.toLowerCase() ?? "")),
    [available, completion?.query],
  );
  const preview = useMemo(
    () => resolveVariablePreview(value, new Map(available.map((variable) => [variable.name, variable.value]))),
    [value, available],
  );
  const showPreview = isFocused && !completion && preview !== null;

  const updatePosition = useCallback(() => {
    const rect = inputRef.current?.getBoundingClientRect();
    if (!rect) return;
    const width = Math.min(window.innerWidth - 16, Math.max(280, rect.width));
    const roomBelow = window.innerHeight - rect.bottom;
    const popupHeight = completion ? 320 : 160;
    setPosition({
      top: roomBelow >= popupHeight ? rect.bottom + 4 : Math.max(8, rect.top - popupHeight - 4),
      left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
      width,
    });
  }, [completion]);

  useLayoutEffect(() => {
    if (!completion && !showPreview) return;
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [completion, showPreview, updatePosition]);

  useEffect(() => setSelectedIndex(0), [completion?.query]);
  useEffect(() => {
    const list = optionsRef.current;
    const option = list?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!list || !option) return;
    const listBounds = list.getBoundingClientRect();
    const optionBounds = option.getBoundingClientRect();
    if (optionBounds.top < listBounds.top) list.scrollTop -= listBounds.top - optionBounds.top;
    else if (optionBounds.bottom > listBounds.bottom) list.scrollTop += optionBounds.bottom - listBounds.bottom;
  }, [selectedIndex, completion?.query]);

  const inspectCaret = (value: string, caret: number) => {
    setCompletion(findVariableCompletion(value, caret));
  };

  const insertVariable = (variable: Variable) => {
    const input = inputRef.current;
    if (!input || !completion) return;
    const current = value;
    const after = current.slice(completion.end);
    const suffix = after.match(/^[A-Za-z0-9_]*\s*}}/);
    const end = completion.end + (suffix?.[0].length ?? 0);
    const replacement = `\${{vars.${variable.name}}}`;
    const next = current.slice(0, completion.start) + replacement + current.slice(end);
    onValueChange(next);
    setCompletion(null);
    requestAnimationFrame(() => {
      input.focus({ preventScroll: true });
      const caret = completion.start + replacement.length;
      input.setSelectionRange(caret, caret);
    });
  };

  const handleChange = (event: ChangeEvent<TextControl>) => {
    onValueChange(event.currentTarget.value);
    inspectCaret(event.currentTarget.value, event.currentTarget.selectionStart ?? 0);
  };

  const handleKeyDown = (event: KeyboardEvent<TextControl>) => {
    if (!completion) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      setCompletion(null);
    } else if (matches.length > 0 && event.key === "ArrowDown") {
      event.preventDefault();
      event.stopPropagation();
      setSelectedIndex((index) => (index + 1) % matches.length);
    } else if (matches.length > 0 && event.key === "ArrowUp") {
      event.preventDefault();
      event.stopPropagation();
      setSelectedIndex((index) => (index - 1 + matches.length) % matches.length);
    } else if (matches.length > 0 && (event.key === "Enter" || event.key === "Tab")) {
      event.preventDefault();
      event.stopPropagation();
      insertVariable(matches[selectedIndex] ?? matches[0]);
    }
  };

  const common = {
    name,
    value,
    className,
    placeholder,
    style,
    onChange: handleChange,
    onKeyDown: handleKeyDown,
    onClick: (event: MouseEvent<TextControl>) =>
      inspectCaret(event.currentTarget.value, event.currentTarget.selectionStart ?? 0),
    onFocus: () => setIsFocused(true),
    onBlur: (event: FocusEvent<TextControl>) => {
      onBlur?.(event);
      setCompletion(null);
      setIsFocused(false);
    },
    onMouseDown,
    onTouchStart,
  };

  return (
    <>
      {as === "textarea"
        ? <textarea {...common} ref={inputRef as Ref<HTMLTextAreaElement>} rows={rows} />
        : <input {...common} ref={inputRef as Ref<HTMLInputElement>} type="text" />}
      {completion && createPortal(
        <div
          role="listbox"
          aria-label="Variables"
          className="fixed z-[9999] overflow-hidden rounded-xl border border-[var(--kai-border)] bg-[var(--kai-surface)] shadow-2xl"
          style={position}
          onMouseDown={(event) => event.preventDefault()}
        >
          <div ref={optionsRef} className="max-h-48 overflow-y-auto p-1">
            {matches.length === 0 ? (
              <div className="px-3 py-2 text-xs text-[var(--kai-text-muted)]">
                {available.length === 0 ? "No variables yet. Add one on the Variables page." : "No matching variables"}
              </div>
            ) : matches.map((variable, index) => (
              <button
                key={variable.id}
                type="button"
                role="option"
                aria-selected={index === selectedIndex}
                className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm ${index === selectedIndex ? "bg-blue-600 text-white" : "text-[var(--kai-text)] hover:bg-[var(--kai-surface-hover)]"}`}
                onMouseEnter={() => setSelectedIndex(index)}
                onClick={() => insertVariable(variable)}
              >
                <span className="min-w-0 truncate font-mono">vars.{variable.name}</span>
                <span className="shrink-0 text-xs opacity-70">{variable.workflow_id ? "Workflow" : "Global"}</span>
              </button>
            ))}
          </div>
          {matches.length > 0 && (
            <div className="border-t border-[var(--kai-border)] px-3 py-2" aria-live="polite">
              <div className="mb-1 text-xs text-[var(--kai-text-muted)]">Selected value</div>
              <div className="max-h-28 overflow-y-auto whitespace-pre-wrap break-all text-sm text-[var(--kai-text)]">
                {matches[selectedIndex]?.value || (matches[selectedIndex]?.value === "" ? "(empty)" : matches[0].value)}
              </div>
            </div>
          )}
        </div>,
        document.body,
      )}
      {showPreview && createPortal(
        <div
          role="status"
          className="fixed z-[9999] max-h-60 overflow-y-auto rounded-xl border border-[var(--kai-border)] bg-[var(--kai-surface)] px-3 py-2 shadow-2xl"
          style={position}
        >
          <div className="mb-1 text-xs text-[var(--kai-text-muted)]">Variable result preview</div>
          <div className="whitespace-pre-wrap break-all text-sm text-[var(--kai-text)]">
            {preview.missing.length > 0
              ? `Variable not found: ${preview.missing.join(", ")}`
              : preview.value || "(empty)"}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
