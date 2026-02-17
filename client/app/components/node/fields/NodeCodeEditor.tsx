import { ErrorMessage, useFormikContext } from "formik";
import type { NodeProperty } from "../types";
import { useRef, useEffect, useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { Maximize2, Minimize2, X, ChevronDown } from "lucide-react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor, languages, IDisposable } from "monaco-editor";
import { completionsByLanguage } from "./monaco/completions";
import {
    PYTHON_VERSIONS,
    DEFAULT_PYTHON_VERSION,
    getPythonDiagnostics,
    getVersionSpecificCompletions,
    type PythonVersion,
} from "./monaco/pythonVersionFeatures";

interface NodeCodeEditorProps {
    property: NodeProperty;
    values: any;
}

function getWordsFromText(text: string): string[] {
    const matches = text.match(/\b[a-zA-Z_]\w{4,}\b/g);
    if (!matches) return [];
    return [...new Set(matches)];
}

export const NodeCodeEditor = ({ property, values }: NodeCodeEditorProps) => {
    const { setFieldValue } = useFormikContext();
    const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
    const disposablesRef = useRef<IDisposable[]>([]);
    const [expanded, setExpanded] = useState(false);
    const [pythonVersion, setPythonVersion] = useState<PythonVersion>(DEFAULT_PYTHON_VERSION);
    const [versionDropdownOpen, setVersionDropdownOpen] = useState(false);
    const [fullscreenVersionDropdownOpen, setFullscreenVersionDropdownOpen] = useState(false);
    const monacoRef = useRef<typeof import("monaco-editor") | null>(null);

    const displayOptions = property?.displayOptions || {};
    const show = displayOptions.show || {};

    // Check display conditions
    if (Object.keys(show).length > 0) {
        for (const [dependencyName, validValue] of Object.entries(show)) {
            const dependencyValue = values[dependencyName];
            if (dependencyValue !== validValue) {
                return null;
            }
        }
    }

    const fullscreenEditorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

    const language = values.language === "javascript" ? "javascript" : "python";
    const inlineHeight = (property.rows || 12) * 24;
    const currentValue = values[property.name] || "";

    const registerCompletions = useCallback(
        (monacoInstance: typeof import("monaco-editor")) => {
            // Dispose previous registrations
            disposablesRef.current.forEach((d) => d.dispose());
            disposablesRef.current = [];

            const staticItems =
                completionsByLanguage[language as keyof typeof completionsByLanguage] || [];

            // Add version-specific completions for Python
            const versionItems =
                language === "python" ? getVersionSpecificCompletions(pythonVersion) : [];

            const disposable = monacoInstance.languages.registerCompletionItemProvider(language, {
                provideCompletionItems: (model, position) => {
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
        [language, pythonVersion]
    );

    const handleEditorMount: OnMount = (editorInstance, monacoInstance) => {
        editorRef.current = editorInstance;
        monacoRef.current = monacoInstance;
        registerCompletions(monacoInstance);
    };

    // Re-register completions when language changes
    useEffect(() => {
        if (editorRef.current) {
            const monacoInstance = (window as any).monaco;
            if (monacoInstance) {
                registerCompletions(monacoInstance);
            }
        }
    }, [language, pythonVersion, registerCompletions]);

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

    // Lock body scroll when fullscreen is open
    useEffect(() => {
        if (expanded) {
            document.body.style.overflow = "hidden";
            return () => {
                document.body.style.overflow = "";
            };
        }
    }, [expanded]);

    // Close fullscreen on Escape, save & close on Ctrl+S
    useEffect(() => {
        if (!expanded) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                setExpanded(false);
            }
            if ((e.ctrlKey || e.metaKey) && e.key === "s") {
                e.preventDefault();
                setExpanded(false);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [expanded]);

    const handleFullscreenMount: OnMount = (editorInstance, monacoInstance) => {
        fullscreenEditorRef.current = editorInstance;
        monacoRef.current = monacoInstance;
        registerCompletions(monacoInstance);
        editorInstance.focus();
    };

    // Reusable version dropdown component
    const VersionDropdown = ({
        isOpen,
        setIsOpen,
    }: {
        isOpen: boolean;
        setIsOpen: (v: boolean) => void;
    }) => {
        if (language !== "python") return null;
        return (
            <div className="relative">
                <button
                    type="button"
                    onClick={() => setIsOpen(!isOpen)}
                    className="flex items-center gap-1 text-xs text-gray-300 bg-[#3c3c3c] hover:bg-[#4c4c4c] px-2 py-0.5 rounded transition-colors"
                >
                    Python {pythonVersion}
                    <ChevronDown size={12} className={`transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </button>
                {isOpen && (
                    <div className="absolute top-full left-0 mt-1 z-50 bg-[#252526] border border-[#3c3c3c] rounded-lg shadow-lg shadow-black/50 overflow-hidden min-w-[120px]">
                        {PYTHON_VERSIONS.map((v) => (
                            <button
                                key={v}
                                type="button"
                                onClick={() => {
                                    setPythonVersion(v);
                                    setIsOpen(false);
                                }}
                                className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                                    v === pythonVersion
                                        ? "bg-blue-600/30 text-blue-300"
                                        : "text-gray-300 hover:bg-[#3c3c3c] hover:text-white"
                                }`}
                            >
                                Python {v}
                                {v === pythonVersion && " ✓"}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        );
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disposablesRef.current.forEach((d) => d.dispose());
            disposablesRef.current = [];
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

    return (
        <div
            className={`${property?.colSpan ? `col-span-${property?.colSpan}` : "col-span-2"}`}
            key={property.name}
        >
            <div className="flex items-center justify-between mb-2">
                <label className="text-white text-sm font-medium flex items-center gap-2">
                    {property.displayName}
                </label>
                <VersionDropdown isOpen={versionDropdownOpen} setIsOpen={setVersionDropdownOpen} />
            </div>

            {/* Inline Editor */}
            <div
                className="relative rounded-lg border border-gray-600 overflow-hidden focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500"
                onMouseDown={(e: any) => e.stopPropagation()}
                onTouchStart={(e: any) => e.stopPropagation()}
                onKeyDown={(e: any) => e.stopPropagation()}
            >
                <button
                    type="button"
                    onClick={() => setExpanded(true)}
                    className="absolute top-1 right-2 z-10 p-1 rounded hover:bg-gray-700/80 text-gray-400 hover:text-white transition-colors"
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

            <ErrorMessage
                name={property.name}
                component="div"
                className="text-red-400 text-sm mt-1"
            />

            {property.description && (
                <p className="text-slate-400 text-xs mt-2">{property.description}</p>
            )}

            {property.hint && (
                <p className="text-slate-400 text-sm mt-1">{property.hint}</p>
            )}

            {property.maxLength && (
                <div className="text-gray-400 text-xs mt-1">
                    Characters: {(values[property.name]?.length || 0).toLocaleString()} /{" "}
                    {property.maxLength.toLocaleString()}
                </div>
            )}

            {/* Fullscreen Modal */}
            {expanded &&
                createPortal(
                    <div
                        className="fixed inset-0 z-[9999] flex flex-col bg-[#1e1e1e]"
                        onMouseDown={(e: any) => e.stopPropagation()}
                        onTouchStart={(e: any) => e.stopPropagation()}
                        onKeyDown={(e: any) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-4 py-2 bg-[#252526] border-b border-[#3c3c3c]">
                            <div className="flex items-center gap-3">
                                <span className="text-white text-sm font-medium">
                                    {property.displayName}
                                </span>
                                <span className="text-xs text-gray-400 bg-[#3c3c3c] px-2 py-0.5 rounded">
                                    {language}
                                </span>
                                <VersionDropdown isOpen={fullscreenVersionDropdownOpen} setIsOpen={setFullscreenVersionDropdownOpen} />
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-500">
                                    Esc to close
                                </span>
                                <button
                                    type="button"
                                    onClick={() => setExpanded(false)}
                                    className="p-1.5 rounded hover:bg-[#3c3c3c] text-gray-400 hover:text-white transition-colors"
                                    title="Close fullscreen"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        {/* Fullscreen Editor */}
                        <div className="flex-1">
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
                    </div>,
                    document.body
                )}
        </div>
    );
};
