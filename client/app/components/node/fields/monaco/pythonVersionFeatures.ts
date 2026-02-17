import type { languages, editor as monacoEditor } from "monaco-editor";

type CompletionItem = Omit<languages.CompletionItem, "range">;

const CompletionItemKind = {
    Function: 1,
    Keyword: 17,
    Snippet: 27,
    Module: 8,
    Constant: 14,
} as const;

const InsertTextRule = {
    InsertAsSnippet: 4,
} as const;

// Python versions available for selection
export const PYTHON_VERSIONS = [
    "3.8",
    "3.9",
    "3.10",
    "3.11",
    "3.12",
    "3.13",
] as const;

export type PythonVersion = (typeof PYTHON_VERSIONS)[number];

export const DEFAULT_PYTHON_VERSION: PythonVersion = "3.11";

// ----- Version-specific syntax patterns for diagnostics -----

interface VersionFeature {
    name: string;
    minVersion: PythonVersion;
    // Regex to detect usage in code
    pattern: RegExp;
    message: string;
}

const VERSION_FEATURES: VersionFeature[] = [
    {
        name: "f-string",
        minVersion: "3.6" as PythonVersion,
        pattern: /\bf(['"])/g,
        message: "f-strings require Python 3.6+",
    },
    {
        name: "walrus-operator",
        minVersion: "3.8",
        pattern: /:=/g,
        message: "Walrus operator (:=) requires Python 3.8+",
    },
    {
        name: "dict-union-operator",
        minVersion: "3.9",
        pattern: /[a-zA-Z_]\w*\s*\|\s*[a-zA-Z_]\w*|[a-zA-Z_]\w*\s*\|=\s*/g,
        message: "Dictionary merge operator (|, |=) requires Python 3.9+",
    },
    {
        name: "match-case",
        minVersion: "3.10",
        pattern: /^\s*match\s+.+\s*:\s*$/gm,
        message: "match/case statement requires Python 3.10+",
    },
    {
        name: "case-statement",
        minVersion: "3.10",
        pattern: /^\s*case\s+.+\s*:\s*$/gm,
        message: "match/case statement requires Python 3.10+",
    },
    {
        name: "exception-groups",
        minVersion: "3.11",
        pattern: /\bexcept\s*\*/g,
        message: "Exception groups (except*) require Python 3.11+",
    },
    {
        name: "type-alias",
        minVersion: "3.12",
        pattern: /^\s*type\s+[A-Z]\w*\s*=/gm,
        message: "type alias statement requires Python 3.12+",
    },
];

function versionToNumber(version: string): number {
    const parts = version.split(".").map(Number);
    return parts[0] * 100 + (parts[1] || 0);
}

/**
 * Returns Monaco editor diagnostic markers for syntax features
 * that are NOT supported in the target Python version.
 */
export function getPythonDiagnostics(
    code: string,
    targetVersion: PythonVersion,
    monacoSeverity: typeof import("monaco-editor").MarkerSeverity
): monacoEditor.IMarkerData[] {
    const markers: monacoEditor.IMarkerData[] = [];
    const targetNum = versionToNumber(targetVersion);

    for (const feature of VERSION_FEATURES) {
        const featureNum = versionToNumber(feature.minVersion);
        if (targetNum >= featureNum) continue; // supported

        const regex = new RegExp(feature.pattern.source, feature.pattern.flags);
        let match: RegExpExecArray | null;

        while ((match = regex.exec(code)) !== null) {
            // Calculate line/column from offset
            const beforeMatch = code.substring(0, match.index);
            const lines = beforeMatch.split("\n");
            const lineNumber = lines.length;
            const column = (lines[lines.length - 1]?.length || 0) + 1;
            const endColumn = column + match[0].length;

            markers.push({
                severity: monacoSeverity.Warning,
                message: `${feature.message} (target: Python ${targetVersion})`,
                startLineNumber: lineNumber,
                startColumn: column,
                endLineNumber: lineNumber,
                endColumn: endColumn,
                source: "Python Version Check",
            });
        }
    }

    return markers;
}

// ----- Version-specific completions -----

interface VersionCompletionSet {
    minVersion: PythonVersion;
    completions: CompletionItem[];
}

const VERSION_COMPLETIONS: VersionCompletionSet[] = [
    {
        minVersion: "3.8",
        completions: [
            {
                label: "walrus operator",
                kind: CompletionItemKind.Snippet,
                insertText: "if (${1:n} := ${2:expr}):\n    ${3:pass}",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Walrus operator (3.8+)",
                documentation: "Assignment expression — assign and test in one step.",
            },
        ],
    },
    {
        minVersion: "3.10",
        completions: [
            {
                label: "match/case",
                kind: CompletionItemKind.Snippet,
                insertText:
                    "match ${1:subject}:\n    case ${2:pattern}:\n        ${3:pass}\n    case _:\n        ${4:pass}",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Structural pattern matching (3.10+)",
                documentation: "Match a value against multiple patterns.",
            },
        ],
    },
    {
        minVersion: "3.11",
        completions: [
            {
                label: "except* (ExceptionGroup)",
                kind: CompletionItemKind.Snippet,
                insertText:
                    "try:\n    ${1:pass}\nexcept* ${2:ValueError} as eg:\n    ${3:pass}",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Exception group handling (3.11+)",
                documentation: "Handle exception groups with except*.",
            },
            {
                label: "ExceptionGroup",
                kind: CompletionItemKind.Function,
                insertText: "ExceptionGroup(${1:message}, [${2:exceptions}])",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Create ExceptionGroup (3.11+)",
            },
            {
                label: "TaskGroup",
                kind: CompletionItemKind.Snippet,
                insertText:
                    "async with asyncio.TaskGroup() as tg:\n    tg.create_task(${1:coro})",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "asyncio.TaskGroup (3.11+)",
            },
            {
                label: "tomllib",
                kind: CompletionItemKind.Module,
                insertText: "import tomllib",
                detail: "Import tomllib module (3.11+)",
            },
        ],
    },
    {
        minVersion: "3.12",
        completions: [
            {
                label: "type alias",
                kind: CompletionItemKind.Snippet,
                insertText: "type ${1:Alias} = ${2:int | str}",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Type alias statement (3.12+)",
                documentation: "Soft keyword `type` for type aliases.",
            },
        ],
    },
];

/**
 * Returns version-specific completion items that are available
 * for the given target Python version.
 */
export function getVersionSpecificCompletions(
    targetVersion: PythonVersion
): CompletionItem[] {
    const targetNum = versionToNumber(targetVersion);
    const items: CompletionItem[] = [];

    for (const set of VERSION_COMPLETIONS) {
        if (versionToNumber(set.minVersion) <= targetNum) {
            items.push(...set.completions);
        }
    }

    return items;
}
