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

// JavaScript ES versions available for selection
export const JAVASCRIPT_VERSIONS = [
    "ES2015",
    "ES2017",
    "ES2018",
    "ES2019",
    "ES2020",
    "ES2021",
    "ES2022",
    "ES2023",
] as const;

export type JavaScriptVersion = (typeof JAVASCRIPT_VERSIONS)[number];

export const DEFAULT_JAVASCRIPT_VERSION: JavaScriptVersion = "ES2022";

// ----- Version-specific syntax patterns for diagnostics -----

interface VersionFeature {
    name: string;
    minVersion: JavaScriptVersion;
    pattern: RegExp;
    message: string;
}

const VERSION_FEATURES: VersionFeature[] = [
    {
        name: "arrow-function",
        minVersion: "ES2015",
        pattern: /=>/g,
        message: "Arrow functions require ES2015+",
    },
    {
        name: "template-literal",
        minVersion: "ES2015",
        pattern: /`[^`]*`/g,
        message: "Template literals require ES2015+",
    },
    {
        name: "let-declaration",
        minVersion: "ES2015",
        pattern: /\blet\s+/g,
        message: "let declarations require ES2015+",
    },
    {
        name: "const-declaration",
        minVersion: "ES2015",
        pattern: /\bconst\s+/g,
        message: "const declarations require ES2015+",
    },
    {
        name: "class-declaration",
        minVersion: "ES2015",
        pattern: /\bclass\s+\w+/g,
        message: "class declarations require ES2015+",
    },
    {
        name: "destructuring",
        minVersion: "ES2015",
        pattern: /(?:const|let|var)\s*\{/g,
        message: "Destructuring assignment requires ES2015+",
    },
    {
        name: "for-of",
        minVersion: "ES2015",
        pattern: /\bfor\s*\([^)]*\bof\b/g,
        message: "for...of loops require ES2015+",
    },
    {
        name: "async-await",
        minVersion: "ES2017",
        pattern: /\basync\s+function\b|\bawait\s+/g,
        message: "async/await requires ES2017+",
    },
    {
        name: "optional-chaining",
        minVersion: "ES2020",
        pattern: /\?\./g,
        message: "Optional chaining (?.) requires ES2020+",
    },
    {
        name: "nullish-coalescing",
        minVersion: "ES2020",
        pattern: /\?\?(?!=)/g,
        message: "Nullish coalescing (??) requires ES2020+",
    },
    {
        name: "logical-assignment-or",
        minVersion: "ES2021",
        pattern: /\|\|=/g,
        message: "Logical OR assignment (||=) requires ES2021+",
    },
    {
        name: "logical-assignment-and",
        minVersion: "ES2021",
        pattern: /&&=/g,
        message: "Logical AND assignment (&&=) requires ES2021+",
    },
    {
        name: "nullish-assignment",
        minVersion: "ES2021",
        pattern: /\?\?=/g,
        message: "Nullish coalescing assignment (??=) requires ES2021+",
    },
    {
        name: "replaceAll",
        minVersion: "ES2021",
        pattern: /\.replaceAll\s*\(/g,
        message: "String.replaceAll() requires ES2021+",
    },
    {
        name: "array-at",
        minVersion: "ES2022",
        pattern: /\.at\s*\(/g,
        message: ".at() requires ES2022+",
    },
    {
        name: "private-fields",
        minVersion: "ES2022",
        pattern: /this\.#\w+|#\w+\s*[=;(]/g,
        message: "Private class fields (#) require ES2022+",
    },
    {
        name: "top-level-await",
        minVersion: "ES2022",
        pattern: /^await\s+/gm,
        message: "Top-level await requires ES2022+",
    },
    {
        name: "findLast",
        minVersion: "ES2023",
        pattern: /\.findLast\s*\(/g,
        message: "Array.findLast() requires ES2023+",
    },
    {
        name: "findLastIndex",
        minVersion: "ES2023",
        pattern: /\.findLastIndex\s*\(/g,
        message: "Array.findLastIndex() requires ES2023+",
    },
];

function versionToNumber(version: JavaScriptVersion): number {
    const year = parseInt(version.replace("ES", ""), 10);
    return year;
}

/**
 * Returns Monaco editor diagnostic markers for syntax features
 * that are NOT supported in the target JavaScript version.
 */
export function getJavaScriptDiagnostics(
    code: string,
    targetVersion: JavaScriptVersion,
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
            const beforeMatch = code.substring(0, match.index);
            const lines = beforeMatch.split("\n");
            const lineNumber = lines.length;
            const column = (lines[lines.length - 1]?.length || 0) + 1;
            const endColumn = column + match[0].length;

            markers.push({
                severity: monacoSeverity.Warning,
                message: `${feature.message} (target: ${targetVersion})`,
                startLineNumber: lineNumber,
                startColumn: column,
                endLineNumber: lineNumber,
                endColumn: endColumn,
                source: "JavaScript Version Check",
            });
        }
    }

    return markers;
}

// ----- Version-specific completions -----

interface VersionCompletionSet {
    minVersion: JavaScriptVersion;
    completions: CompletionItem[];
}

const VERSION_COMPLETIONS: VersionCompletionSet[] = [
    {
        minVersion: "ES2015",
        completions: [
            {
                label: "arrow function",
                kind: CompletionItemKind.Snippet,
                insertText: "const ${1:name} = (${2:params}) => {\n\t${3}\n};",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Arrow function (ES2015+)",
                documentation: "Create an arrow function expression.",
            },
            {
                label: "class",
                kind: CompletionItemKind.Snippet,
                insertText:
                    "class ${1:Name} {\n\tconstructor(${2:params}) {\n\t\t${3}\n\t}\n}",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Class declaration (ES2015+)",
                documentation: "Create an ES2015 class.",
            },
            {
                label: "template literal",
                kind: CompletionItemKind.Snippet,
                insertText: "`${1:text} \\${${2:expression}}`",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Template literal (ES2015+)",
                documentation: "String with embedded expressions.",
            },
            {
                label: "Promise",
                kind: CompletionItemKind.Snippet,
                insertText:
                    "new Promise((resolve, reject) => {\n\t${1}\n});",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Promise constructor (ES2015+)",
                documentation: "Create a new Promise.",
            },
            {
                label: "destructuring",
                kind: CompletionItemKind.Snippet,
                insertText: "const { ${1:prop} } = ${2:object};",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Destructuring assignment (ES2015+)",
                documentation: "Extract values from objects or arrays.",
            },
        ],
    },
    {
        minVersion: "ES2017",
        completions: [
            {
                label: "async/await function",
                kind: CompletionItemKind.Snippet,
                insertText:
                    "async function ${1:name}(${2:params}) {\n\tconst ${3:result} = await ${4:promise};\n\treturn ${3:result};\n}",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Async function (ES2017+)",
                documentation: "Create an async function with await.",
            },
        ],
    },
    {
        minVersion: "ES2020",
        completions: [
            {
                label: "optional chaining",
                kind: CompletionItemKind.Snippet,
                insertText: "${1:obj}?.${2:prop}",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Optional chaining (ES2020+)",
                documentation:
                    "Access nested properties safely without checking each level.",
            },
            {
                label: "nullish coalescing",
                kind: CompletionItemKind.Snippet,
                insertText: "${1:value} ?? ${2:default}",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Nullish coalescing (ES2020+)",
                documentation:
                    "Provide a default for null or undefined (but not for 0 or empty string).",
            },
            {
                label: "Promise.allSettled",
                kind: CompletionItemKind.Function,
                insertText: "Promise.allSettled([${1:promises}])",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Promise.allSettled (ES2020+)",
                documentation:
                    "Wait for all promises to settle (resolve or reject).",
            },
        ],
    },
    {
        minVersion: "ES2021",
        completions: [
            {
                label: "logical assignment (||=)",
                kind: CompletionItemKind.Snippet,
                insertText: "${1:variable} ||= ${2:value};",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Logical OR assignment (ES2021+)",
                documentation: "Assign if the variable is falsy.",
            },
            {
                label: "replaceAll",
                kind: CompletionItemKind.Function,
                insertText: "${1:str}.replaceAll(${2:search}, ${3:replacement})",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "String.replaceAll (ES2021+)",
                documentation: "Replace all occurrences of a string.",
            },
            {
                label: "Promise.any",
                kind: CompletionItemKind.Function,
                insertText: "Promise.any([${1:promises}])",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Promise.any (ES2021+)",
                documentation:
                    "Resolves when any promise fulfills; rejects if all reject.",
            },
        ],
    },
    {
        minVersion: "ES2022",
        completions: [
            {
                label: "Array.at",
                kind: CompletionItemKind.Function,
                insertText: "${1:array}.at(${2:index})",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Array.at (ES2022+)",
                documentation:
                    "Access elements by index, including negative indices.",
            },
            {
                label: "Object.hasOwn",
                kind: CompletionItemKind.Function,
                insertText: "Object.hasOwn(${1:obj}, ${2:prop})",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Object.hasOwn (ES2022+)",
                documentation:
                    "Check if an object has a property (replaces hasOwnProperty).",
            },
            {
                label: "structuredClone",
                kind: CompletionItemKind.Function,
                insertText: "structuredClone(${1:value})",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "structuredClone (ES2022+)",
                documentation: "Deep clone a value using the structured clone algorithm.",
            },
        ],
    },
    {
        minVersion: "ES2023",
        completions: [
            {
                label: "Array.findLast",
                kind: CompletionItemKind.Function,
                insertText: "${1:array}.findLast((${2:item}) => ${3:condition})",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Array.findLast (ES2023+)",
                documentation:
                    "Find the last element matching a condition.",
            },
            {
                label: "Array.findLastIndex",
                kind: CompletionItemKind.Function,
                insertText:
                    "${1:array}.findLastIndex((${2:item}) => ${3:condition})",
                insertTextRules: InsertTextRule.InsertAsSnippet,
                detail: "Array.findLastIndex (ES2023+)",
                documentation:
                    "Find the index of the last element matching a condition.",
            },
        ],
    },
];

/**
 * Returns version-specific completion items that are available
 * for the given target JavaScript version.
 */
export function getJavaScriptVersionSpecificCompletions(
    targetVersion: JavaScriptVersion
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
