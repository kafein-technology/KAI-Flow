import { ErrorMessage, useFormikContext } from "formik";
import type { NodeProperty } from "../types";
import { useRef, useEffect, useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { Maximize2, X } from "lucide-react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor, languages, IDisposable } from "monaco-editor";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";
import { completionsByLanguage } from "./monaco/completions";
import { findVariableCompletion } from "./variableCompletion";
import { useVariableStore } from "~/stores/variables";
import { useWorkflows } from "~/stores/workflows";
import type { Variable } from "~/types/api";
import {
    getPythonDiagnostics,
    getVersionSpecificCompletions,
    type PythonVersion,
} from "./monaco/pythonVersionFeatures";
import {
    getJavaScriptDiagnostics,
    getJavaScriptVersionSpecificCompletions,
    type JavaScriptVersion,
} from "./monaco/javascriptVersionFeatures";

interface NodeCodeEditorProps {
    property: NodeProperty;
    values: any;
}

type PickerState = { mode: "automatic" | "manual" | "preview"; editor: "inline" | "fullscreen"; query: string };

function scopedVariables(variables: Variable[], workflowId: string | undefined): Variable[] {
    const byName = new Map<string, Variable>();
    for (const variable of variables) {
        if (variable.workflow_id === null) byName.set(variable.name, variable);
    }
    for (const variable of variables) {
        if (workflowId && variable.workflow_id === workflowId) byName.set(variable.name, variable);
    }
    return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

function CodeVariablePicker({
    mode, query, matches, selectedIndex, onQueryChange, onSelect, onSelectedIndexChange, onClose,
}: {
    mode: PickerState["mode"];
    query: string;
    matches: Variable[];
    selectedIndex: number;
    onQueryChange: (query: string) => void;
    onSelect: (variable: Variable) => void;
    onSelectedIndexChange: (index: number) => void;
    onClose: () => void;
}) {
    const listRef = useRef<HTMLDivElement>(null);
    const searchRef = useRef<HTMLInputElement>(null);
    const selected = matches[selectedIndex] ?? matches[0];
    useEffect(() => {
        if (mode === "manual") searchRef.current?.focus({ preventScroll: true });
    }, [mode]);
    useEffect(() => {
        const list = listRef.current;
        const option = list?.querySelector<HTMLElement>('[aria-selected="true"]');
        if (!list || !option) return;
        const listBounds = list.getBoundingClientRect();
        const optionBounds = option.getBoundingClientRect();
        if (optionBounds.top < listBounds.top) list.scrollTop -= listBounds.top - optionBounds.top;
        else if (optionBounds.bottom > listBounds.bottom) list.scrollTop += optionBounds.bottom - listBounds.bottom;
    }, [selectedIndex, query]);
    return (
        <div className="mt-2 rounded-lg border border-[var(--kai-border)] bg-[var(--kai-surface-control)] p-2" aria-label="Code variables">
            {mode === "manual" ? (
                <input
                    ref={searchRef}
                    type="search"
                    aria-label="Search code variables"
                    value={query}
                    onChange={(event) => onQueryChange(event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key === "Escape") {
                            event.preventDefault();
                            event.stopPropagation();
                            onClose();
                        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                            event.preventDefault();
                            onSelectedIndexChange((selectedIndex + (event.key === "ArrowDown" ? 1 : matches.length - 1)) % Math.max(matches.length, 1));
                        } else if (event.key === "Enter") {
                            event.preventDefault();
                            if (selected) onSelect(selected);
                        }
                    }}
                    placeholder="Search variables..."
                    className="kai-node-field-control mb-2 w-full px-3 py-2 text-sm"
                />
            ) : mode === "automatic" ? (
                <div className="mb-2 text-xs text-[var(--kai-text-muted)]">Variables · keep typing to filter, then use ↑ ↓ and Enter</div>
            ) : (
                <div className="mb-2 text-xs text-[var(--kai-text-muted)]">Inserted variable · value shown below</div>
            )}
            <div ref={listRef} role="listbox" aria-label="Code variable suggestions" className="max-h-36 overflow-y-auto">
                {matches.length === 0 ? (
                    <div className="px-2 py-2 text-xs text-[var(--kai-text-muted)]">{query ? "No matching variables" : "No variables yet. Add one on the Variables page."}</div>
                ) : matches.map((variable, index) => (
                    <button
                        key={variable.id}
                        type="button"
                        role="option"
                        aria-selected={index === selectedIndex}
                        onMouseDown={(event) => event.preventDefault()}
                        onMouseEnter={() => onSelectedIndexChange(index)}
                        onClick={() => onSelect(variable)}
                        className={`flex w-full items-center justify-between gap-3 rounded px-2 py-1.5 text-left text-sm ${index === selectedIndex ? "bg-blue-600 text-white" : "text-[var(--kai-text)] hover:bg-[var(--kai-surface-hover)]"}`}
                    >
                        <span className="min-w-0 truncate font-mono">vars.{variable.name}</span>
                        <span className="shrink-0 text-xs opacity-70">{variable.workflow_id ? "Workflow" : "Global"}</span>
                    </button>
                ))}
            </div>
            {selected && (
                <div className="mt-2 border-t border-[var(--kai-border)] pt-2">
                    <div className="mb-1 text-xs text-[var(--kai-text-muted)]">Selected value</div>
                    <div className="max-h-28 overflow-y-auto whitespace-pre-wrap break-all text-sm text-[var(--kai-text)]">{selected.value || "(empty)"}</div>
                </div>
            )}
        </div>
    );
}

function getWordsFromText(text: string): string[] {
    const matches = text.match(/\b[a-zA-Z_]\w{4,}\b/g);
    if (!matches) return [];
    return [...new Set(matches)];
}

export const NodeCodeEditor = ({ property, values }: NodeCodeEditorProps) => {
    const { setFieldValue, submitForm } = useFormikContext();
    const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
    const disposablesRef = useRef<IDisposable[]>([]);
    const [expanded, setExpanded] = useState(false);
    const [picker, setPicker] = useState<PickerState | null>(null);
    const pickerRef = useRef<PickerState | null>(null);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const selectedIndexRef = useRef(0);
    const variables = useVariableStore((state) => state.variables);
    const workflowId = useWorkflows((state) => state.currentWorkflow?.id);
    const pythonVersion: PythonVersion = "3.11";
    const javascriptVersion: JavaScriptVersion = "ES2022";
    const monacoRef = useRef<typeof import("monaco-editor") | null>(null);

    const displayOptions = property?.displayOptions || {};
    const show = displayOptions.show || {};
    const isVisible = Object.entries(show).every(([dependencyName, validValue]) => values[dependencyName] === validValue);

    const fullscreenEditorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

    const language = values.language === "javascript" ? "javascript" : "python";
    const inlineHeight = (property.rows || 12) * 24;
    const currentValue = values[property.name] || "";
    const available = scopedVariables(variables, workflowId);
    const matches = available.filter((variable) => variable.name.toLowerCase().includes(picker?.query.toLowerCase() ?? ""));

    const selectIndex = (index: number) => {
        selectedIndexRef.current = index;
        setSelectedIndex(index);
    };

    const updatePicker = (next: PickerState | null) => {
        if (pickerRef.current?.query !== next?.query || pickerRef.current?.mode !== next?.mode) selectIndex(0);
        pickerRef.current = next;
        setPicker(next);
    };

    const editorFor = (kind: PickerState["editor"]) =>
        kind === "fullscreen" ? fullscreenEditorRef.current : editorRef.current;

    const insertVariable = (variable: Variable, kind: PickerState["editor"]) => {
        const target = editorFor(kind);
        const model = target?.getModel();
        const position = target?.getPosition();
        if (!target || !model || !position) return;

        const line = model.getLineContent(position.lineNumber);
        const completion = pickerRef.current?.mode === "automatic"
            ? findVariableCompletion(line, position.column - 1)
            : null;
        const suffix = completion ? line.slice(position.column - 1).match(/^[A-Za-z0-9_]*\s*}}/) : null;
        const selection = target.getSelection();
        const range = completion ? {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: completion.start + 1,
            endColumn: position.column + (suffix?.[0].length ?? 0),
        } : selection ?? {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: position.column,
            endColumn: position.column,
        };
        const text = `\${{vars.${variable.name}}}`;
        target.executeEdits("variable-picker", [{ range, text, forceMoveMarkers: true }]);
        target.setPosition({ lineNumber: range.startLineNumber, column: range.startColumn + text.length });
        updatePicker({ mode: "preview", editor: kind, query: variable.name });
        target.getDomNode()?.querySelector<HTMLTextAreaElement>("textarea")?.focus({ preventScroll: true });
    };

    const syncAutomaticPicker = (target: editor.IStandaloneCodeEditor, kind: PickerState["editor"]) => {
        const position = target.getPosition();
        const line = position ? target.getModel()?.getLineContent(position.lineNumber) : undefined;
        const completion = line && position ? findVariableCompletion(line, position.column - 1) : null;
        if (completion) {
            if (pickerRef.current?.mode !== "manual") {
                const current = pickerRef.current;
                if (current?.mode !== "automatic" || current.editor !== kind || current.query !== completion.query) {
                    updatePicker({ mode: "automatic", editor: kind, query: completion.query });
                }
            }
        } else if (pickerRef.current?.mode === "automatic" && pickerRef.current.editor === kind) {
            updatePicker(null);
        }
    };

    const watchEditor = (target: editor.IStandaloneCodeEditor, kind: PickerState["editor"]) => {
        const subscriptions = [
            target.onDidChangeCursorPosition(() => syncAutomaticPicker(target, kind)),
            target.onDidChangeModelContent(() => syncAutomaticPicker(target, kind)),
        ];
        const domNode = target.getDomNode();
        const onKeyDown = (event: globalThis.KeyboardEvent) => {
            const active = pickerRef.current;
            if (active?.mode !== "automatic" || active.editor !== kind) return;
            if (!["ArrowDown", "ArrowUp", "Enter", "Tab", "Escape"].includes(event.key)) return;
            if (event.key === "Escape") {
                event.preventDefault();
                event.stopImmediatePropagation();
                updatePicker(null);
                return;
            }
            const scoped = scopedVariables(useVariableStore.getState().variables, useWorkflows.getState().currentWorkflow?.id);
            const filtered = scoped.filter((variable) => variable.name.toLowerCase().includes(active.query.toLowerCase()));
            if (filtered.length === 0) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            if (event.key === "ArrowDown") selectIndex((selectedIndexRef.current + 1) % filtered.length);
            else if (event.key === "ArrowUp") selectIndex((selectedIndexRef.current - 1 + filtered.length) % filtered.length);
            else insertVariable(filtered[selectedIndexRef.current] ?? filtered[0], kind);
        };
        domNode?.addEventListener("keydown", onKeyDown, true);
        syncAutomaticPicker(target, kind);
        return () => {
            subscriptions.forEach((subscription) => subscription.dispose());
            domNode?.removeEventListener("keydown", onKeyDown, true);
        };
    };

    const registerCompletions = useCallback(
        (monacoInstance: typeof import("monaco-editor")) => {
            // Dispose previous registrations
            disposablesRef.current.forEach((d) => d.dispose());
            disposablesRef.current = [];

            const staticItems =
                completionsByLanguage[language as keyof typeof completionsByLanguage] || [];

            // Add version-specific completions for Python / JavaScript
            const versionItems =
                language === "python"
                    ? getVersionSpecificCompletions(pythonVersion)
                    : language === "javascript"
                        ? getJavaScriptVersionSpecificCompletions(javascriptVersion)
                        : [];

            const disposable = monacoInstance.languages.registerCompletionItemProvider(language, {
                triggerCharacters: ["{", "."],
                provideCompletionItems: (model, position) => {
                    const line = model.getLineContent(position.lineNumber);
                    const completion = findVariableCompletion(line, position.column - 1);
                    if (completion) {
                        return { suggestions: [] };
                    }
                    const word = model.getWordUntilPosition(position);
                    const range = {
                        startLineNumber: position.lineNumber,
                        endLineNumber: position.lineNumber,
                        startColumn: word.startColumn,
                        endColumn: word.endColumn,
                    };

                    // Static + version-specific completions
                    const suggestions: languages.CompletionItem[] = [
                        ...staticItems,
                        ...versionItems,
                    ].map((item) => ({
                        ...item,
                        range,
                    }));

                    // Session-based completions (words from current text)
                    const fullText = model.getValue();
                    const words = getWordsFromText(fullText);
                    const existingLabels = new Set(suggestions.map((s) => s.label as string));

                    for (const w of words) {
                        if (!existingLabels.has(w) && w !== word.word && w.length > word.word.length) {
                            suggestions.push({
                                label: w,
                                kind: monacoInstance.languages.CompletionItemKind.Text,
                                insertText: w,
                                range,
                                detail: "from editor",
                            });
                        }
                    }

                    return { suggestions };
                },
            });

            disposablesRef.current.push(disposable);
        },
        [language, pythonVersion, javascriptVersion]
    );

    const handleEditorMount: OnMount = (editorInstance, monacoInstance) => {
        editorRef.current = editorInstance;
        monacoRef.current = monacoInstance;
        registerCompletions(monacoInstance);
        const stopWatching = watchEditor(editorInstance, "inline");

        // Custom drag & drop handler to prevent Monaco snippet formatting bug
        const domNode = editorInstance.getDomNode();
        if (domNode) {
            const handleDragOver = (e: DragEvent) => {
                e.preventDefault();
            };
            const handleDrop = (e: DragEvent) => {
                const text = e.dataTransfer?.getData("text/plain");
                if (text) {
                    e.preventDefault();
                    e.stopPropagation();
                    const target = editorInstance.getTargetAtClientPoint(e.clientX, e.clientY);
                    if (target && target.position) {
                        const { lineNumber, column } = target.position;
                        editorInstance.executeEdits("drag-drop", [
                            {
                                range: new monacoInstance.Range(lineNumber, column, lineNumber, column),
                                text: text,
                                forceMoveMarkers: true,
                            }
                        ]);
                        editorInstance.setPosition({ lineNumber, column: column + text.length });
                        editorInstance.focus();
                    }
                }
            };
            domNode.addEventListener("dragover", handleDragOver);
            domNode.addEventListener("drop", handleDrop);
            (editorInstance as any)._dropCleanup = () => {
                domNode.removeEventListener("dragover", handleDragOver);
                domNode.removeEventListener("drop", handleDrop);
                stopWatching();
            };
        } else {
            (editorInstance as any)._dropCleanup = stopWatching;
        }

        // Ctrl+S: save & close
        editorInstance.addCommand(
            monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyS,
            () => {
                submitForm();
            }
        );
    };

    // Re-register completions when language changes
    useEffect(() => {
        if (editorRef.current) {
            const monacoInstance = (window as any).monaco;
            if (monacoInstance) {
                registerCompletions(monacoInstance);
            }
        }
    }, [language, pythonVersion, javascriptVersion, registerCompletions]);

    // Run Python version diagnostics whenever code or version changes
    useEffect(() => {
        if (language !== "python" || !monacoRef.current) return;

        const monaco = monacoRef.current;
        const model = editorRef.current?.getModel() || fullscreenEditorRef.current?.getModel();
        if (!model) return;

        const markers = getPythonDiagnostics(
            currentValue,
            pythonVersion,
            monaco.MarkerSeverity
        );
        monaco.editor.setModelMarkers(model, "python-version-check", markers);

        return () => {
            if (model && !model.isDisposed()) {
                monaco.editor.setModelMarkers(model, "python-version-check", []);
            }
        };
    }, [currentValue, pythonVersion, language]);

    // Run JavaScript version diagnostics whenever code or version changes
    useEffect(() => {
        if (language !== "javascript" || !monacoRef.current) return;

        const monaco = monacoRef.current;
        const model = editorRef.current?.getModel() || fullscreenEditorRef.current?.getModel();
        if (!model) return;

        const markers = getJavaScriptDiagnostics(
            currentValue,
            javascriptVersion,
            monaco.MarkerSeverity
        );
        monaco.editor.setModelMarkers(model, "javascript-version-check", markers);

        return () => {
            if (model && !model.isDisposed()) {
                monaco.editor.setModelMarkers(model, "javascript-version-check", []);
            }
        };
    }, [currentValue, javascriptVersion, language]);

    // Lock body scroll when fullscreen is open
    useEffect(() => {
        if (expanded) {
            document.body.style.overflow = "hidden";
            return () => {
                document.body.style.overflow = "";
            };
        }
    }, [expanded]);

    // Close fullscreen on Escape
    useEffect(() => {
        if (!expanded) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                setExpanded(false);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [expanded]);

    useEffect(() => {
        if (expanded || !fullscreenEditorRef.current) return;
        (fullscreenEditorRef.current as editor.IStandaloneCodeEditor & { _dropCleanup?: () => void })._dropCleanup?.();
        fullscreenEditorRef.current = null;
    }, [expanded]);

    const handleFullscreenMount: OnMount = (editorInstance, monacoInstance) => {
        fullscreenEditorRef.current = editorInstance;
        monacoRef.current = monacoInstance;
        registerCompletions(monacoInstance);
        const inlinePosition = editorRef.current?.getPosition();
        if (inlinePosition) editorInstance.setPosition(inlinePosition);
        const stopWatching = watchEditor(editorInstance, "fullscreen");
        editorInstance.focus();

        // Custom drag & drop handler for fullscreen mode
        const domNode = editorInstance.getDomNode();
        if (domNode) {
            const handleDragOver = (e: DragEvent) => {
                e.preventDefault();
            };
            const handleDrop = (e: DragEvent) => {
                const text = e.dataTransfer?.getData("text/plain");
                if (text) {
                    e.preventDefault();
                    e.stopPropagation();
                    const target = editorInstance.getTargetAtClientPoint(e.clientX, e.clientY);
                    if (target && target.position) {
                        const { lineNumber, column } = target.position;
                        editorInstance.executeEdits("drag-drop", [
                            {
                                range: new monacoInstance.Range(lineNumber, column, lineNumber, column),
                                text: text,
                                forceMoveMarkers: true,
                            }
                        ]);
                        editorInstance.setPosition({ lineNumber, column: column + text.length });
                        editorInstance.focus();
                    }
                }
            };
            domNode.addEventListener("dragover", handleDragOver);
            domNode.addEventListener("drop", handleDrop);
            (editorInstance as any)._dropCleanup = () => {
                domNode.removeEventListener("dragover", handleDragOver);
                domNode.removeEventListener("drop", handleDrop);
                stopWatching();
            };
        } else {
            (editorInstance as any)._dropCleanup = stopWatching;
        }

        // Ctrl+S: save & close fullscreen + submit form
        editorInstance.addCommand(
            monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyS,
            () => {
                setExpanded(false);
                submitForm();
            }
        );
    };

    // Fixed version badge (non-editable)
    const VersionBadge = () => {
        if (language === "python") {
            return (
                <span className="rounded bg-[var(--kai-surface-hover)] px-2 py-0.5 text-xs text-[var(--kai-text-secondary)]">
                    Python {pythonVersion}
                </span>
            );
        }
        if (language === "javascript") {
            return (
                <span className="rounded bg-[var(--kai-surface-hover)] px-2 py-0.5 text-xs text-[var(--kai-text-secondary)]">
                    JavaScript {javascriptVersion}
                </span>
            );
        }
        return null;
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disposablesRef.current.forEach((d) => d.dispose());
            disposablesRef.current = [];
            if (editorRef.current && (editorRef.current as any)._dropCleanup) {
                (editorRef.current as any)._dropCleanup();
            }
            if (fullscreenEditorRef.current && (fullscreenEditorRef.current as any)._dropCleanup) {
                (fullscreenEditorRef.current as any)._dropCleanup();
            }
        };
    }, []);

    const handleChange = (value: string | undefined) => {
        setFieldValue(property.name, value || "");
    };

    const editorOptions: editor.IStandaloneEditorConstructionOptions = {
        minimap: { enabled: false },
        fontSize: 13,
        lineHeight: 24,
        tabSize: 2,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        wordWrap: "on",
        padding: { top: 8, bottom: 8 },
        suggestOnTriggerCharacters: true,
        tabCompletion: "on",
        acceptSuggestionOnEnter: "on",
        quickSuggestions: true,
        scrollbar: {
            verticalScrollbarSize: 8,
            horizontalScrollbarSize: 8,
        },
        overviewRulerLanes: 0,
        hideCursorInOverviewRuler: true,
        overviewRulerBorder: false,
        renderLineHighlight: "line",
        contextmenu: true,
        fixedOverflowWidgets: true,
    };

    if (!isVisible) return null;

    return (
        <div
            className={`${property?.colSpan ? `col-span-${property?.colSpan}` : "col-span-2"}`}
            key={property.name}
        >
            <div className="flex items-center justify-between mb-2">
                <FieldLabel
                    label={property.displayName}
                    helpText={getFieldHelpText(property)}
                    className="mb-0 text-sm font-medium text-[var(--kai-text-soft)]"
                />
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        aria-expanded={picker?.editor === "inline"}
                        onClick={() => updatePicker(picker?.editor === "inline" ? null : { mode: "manual", editor: "inline", query: "" })}
                        className="rounded border border-[var(--kai-border)] px-2 py-1 text-xs text-[var(--kai-text)] hover:bg-[var(--kai-surface-hover)]"
                    >
                        Variables
                    </button>
                    <VersionBadge />
                </div>
            </div>

            {/* Inline Editor */}
            <div
                className="relative overflow-hidden rounded-lg border border-[var(--kai-field-border)] transition-colors focus-within:border-[var(--kai-accent)] focus-within:ring-2 focus-within:ring-[var(--kai-accent-soft)]"
                onMouseDown={(e: any) => e.stopPropagation()}
                onTouchStart={(e: any) => e.stopPropagation()}
                onKeyDown={(e: any) => e.stopPropagation()}
            >
                <button
                    type="button"
                    onClick={() => { updatePicker(null); setExpanded(true); }}
                    className="absolute right-2 top-1 z-10 rounded p-1 text-[var(--kai-text-muted)] transition-colors hover:bg-[var(--kai-surface-hover)] hover:text-[var(--kai-text)]"
                    title="Expand editor"
                >
                    <Maximize2 size={14} />
                </button>
                <Editor
                    height={inlineHeight}
                    language={language}
                    theme="vs-dark"
                    value={currentValue}
                    onChange={handleChange}
                    onMount={handleEditorMount}
                    options={editorOptions}
                />
            </div>

            {picker?.editor === "inline" && (
                <CodeVariablePicker
                    mode={picker.mode}
                    query={picker.query}
                    matches={matches}
                    selectedIndex={selectedIndex}
                    onQueryChange={(query) => updatePicker({ ...picker, query })}
                    onSelectedIndexChange={selectIndex}
                    onSelect={(variable) => insertVariable(variable, "inline")}
                    onClose={() => updatePicker(null)}
                />
            )}

            <ErrorMessage
                name={property.name}
                component="div"
                className="kai-node-field-error mt-1"
            />

            {property.maxLength && (
                <div className="kai-node-field-hint mt-1">
                    Characters: {(values[property.name]?.length || 0).toLocaleString()} /{" "}
                    {property.maxLength.toLocaleString()}
                </div>
            )}

            {/* Fullscreen Modal */}
            {expanded &&
                createPortal(
                    <div
                        className="fixed inset-0 z-[9999] flex flex-col bg-[var(--kai-node-modal-bg)]"
                        onMouseDown={(e: any) => e.stopPropagation()}
                        onTouchStart={(e: any) => e.stopPropagation()}
                        onKeyDown={(e: any) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between border-b border-[var(--kai-border-strong)] bg-[var(--kai-surface-control)] px-4 py-2">
                            <div className="flex items-center gap-3">
                                <span className="text-sm font-medium text-[var(--kai-text)]">
                                    {property.displayName}
                                </span>
                                <span className="rounded bg-[var(--kai-surface-hover)] px-2 py-0.5 text-xs text-[var(--kai-text-muted)]">
                                    {language}
                                </span>
                                <VersionBadge />
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    aria-expanded={picker?.editor === "fullscreen"}
                                    onClick={() => updatePicker(picker?.editor === "fullscreen" ? null : { mode: "manual", editor: "fullscreen", query: "" })}
                                    className="rounded border border-[var(--kai-border)] px-2 py-1 text-xs text-[var(--kai-text)] hover:bg-[var(--kai-surface-hover)]"
                                >
                                    Variables
                                </button>
                                <span className="text-xs text-[var(--kai-text-muted)]">
                                    Esc to close
                                </span>
                                <button
                                    type="button"
                                    onClick={() => setExpanded(false)}
                                    className="rounded p-1.5 text-[var(--kai-text-muted)] transition-colors hover:bg-[var(--kai-surface-hover)] hover:text-[var(--kai-text)]"
                                    title="Close fullscreen"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        {/* Fullscreen Editor */}
                        <div className="min-h-0 flex-1 overflow-hidden">
                            <Editor
                                height="100%"
                                language={language}
                                theme="vs-dark"
                                value={currentValue}
                                onChange={handleChange}
                                onMount={handleFullscreenMount}
                                options={{
                                    ...editorOptions,
                                    fontSize: 14,
                                    lineHeight: 22,
                                    minimap: { enabled: true },
                                    padding: { top: 16, bottom: 16 },
                                }}
                            />
                        </div>

                        {picker?.editor === "fullscreen" && (
                            <CodeVariablePicker
                                mode={picker.mode}
                                query={picker.query}
                                matches={matches}
                                selectedIndex={selectedIndex}
                                onQueryChange={(query) => updatePicker({ ...picker, query })}
                                onSelectedIndexChange={selectIndex}
                                onSelect={(variable) => insertVariable(variable, "fullscreen")}
                                onClose={() => updatePicker(null)}
                            />
                        )}
                    </div>,
                    document.body
                )}
        </div>
    );
};
