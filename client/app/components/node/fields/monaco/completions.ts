import type { languages } from "monaco-editor";

type CompletionItem = Omit<languages.CompletionItem, "range">;

const CompletionItemKind = {
    Function: 1,
    Variable: 5,
    Keyword: 17,
    Snippet: 27,
    Module: 8,
    Method: 0,
    Property: 9,
    Constant: 14,
} as const;

const InsertTextRule = {
    InsertAsSnippet: 4,
} as const;

// KAI-Fusion specific variables available in code nodes
const kaiFusionCompletions: CompletionItem[] = [
    {
        label: "node_data",
        kind: CompletionItemKind.Variable,
        detail: "Input data from previous nodes",
        insertText: "node_data",
        documentation: "Contains the output data passed from connected upstream nodes.",
    },
    {
        label: "output",
        kind: CompletionItemKind.Variable,
        detail: "Output variable",
        insertText: "output",
        documentation: "Variable to store the output data that will be passed to downstream nodes.",
    },
    {
        label: "result",
        kind: CompletionItemKind.Variable,
        detail: "Result variable",
        insertText: "result",
        documentation: "Variable to store the final result of the code execution.",
    },
];

const pythonCompletions: CompletionItem[] = [
    // Built-in functions
    { label: "print", kind: CompletionItemKind.Function, insertText: "print(${1:value})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Print to stdout" },
    { label: "len", kind: CompletionItemKind.Function, insertText: "len(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return length of object" },
    { label: "range", kind: CompletionItemKind.Function, insertText: "range(${1:stop})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Generate range of numbers" },
    { label: "str", kind: CompletionItemKind.Function, insertText: "str(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Convert to string" },
    { label: "int", kind: CompletionItemKind.Function, insertText: "int(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Convert to integer" },
    { label: "float", kind: CompletionItemKind.Function, insertText: "float(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Convert to float" },
    { label: "list", kind: CompletionItemKind.Function, insertText: "list(${1:iterable})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Convert to list" },
    { label: "dict", kind: CompletionItemKind.Function, insertText: "dict(${1:})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Create dictionary" },
    { label: "type", kind: CompletionItemKind.Function, insertText: "type(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return type of object" },
    { label: "isinstance", kind: CompletionItemKind.Function, insertText: "isinstance(${1:obj}, ${2:type})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Check instance type" },
    { label: "enumerate", kind: CompletionItemKind.Function, insertText: "enumerate(${1:iterable})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Enumerate iterable" },
    { label: "zip", kind: CompletionItemKind.Function, insertText: "zip(${1:iter1}, ${2:iter2})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Zip iterables together" },
    { label: "map", kind: CompletionItemKind.Function, insertText: "map(${1:func}, ${2:iterable})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Apply function to iterable" },
    { label: "filter", kind: CompletionItemKind.Function, insertText: "filter(${1:func}, ${2:iterable})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Filter iterable" },
    { label: "sorted", kind: CompletionItemKind.Function, insertText: "sorted(${1:iterable})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return sorted list" },
    { label: "abs", kind: CompletionItemKind.Function, insertText: "abs(${1:x})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return absolute value" },
    { label: "max", kind: CompletionItemKind.Function, insertText: "max(${1:iterable})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return maximum value" },
    { label: "min", kind: CompletionItemKind.Function, insertText: "min(${1:iterable})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return minimum value" },
    { label: "sum", kind: CompletionItemKind.Function, insertText: "sum(${1:iterable})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return sum of iterable" },
    { label: "input", kind: CompletionItemKind.Function, insertText: "input(${1:prompt})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Read input from stdin" },
    { label: "open", kind: CompletionItemKind.Function, insertText: "open(${1:file}, ${2:mode})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Open file" },
    { label: "hasattr", kind: CompletionItemKind.Function, insertText: "hasattr(${1:obj}, ${2:name})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Check if object has attribute" },
    { label: "getattr", kind: CompletionItemKind.Function, insertText: "getattr(${1:obj}, ${2:name})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Get attribute from object" },
    // Common modules
    { label: "import json", kind: CompletionItemKind.Module, insertText: "import json", detail: "Import json module" },
    { label: "import os", kind: CompletionItemKind.Module, insertText: "import os", detail: "Import os module" },
    { label: "import sys", kind: CompletionItemKind.Module, insertText: "import sys", detail: "Import sys module" },
    { label: "import re", kind: CompletionItemKind.Module, insertText: "import re", detail: "Import re module" },
    { label: "import math", kind: CompletionItemKind.Module, insertText: "import math", detail: "Import math module" },
    { label: "import datetime", kind: CompletionItemKind.Module, insertText: "import datetime", detail: "Import datetime module" },
    { label: "import requests", kind: CompletionItemKind.Module, insertText: "import requests", detail: "Import requests module" },
    // Snippets
    { label: "for loop", kind: CompletionItemKind.Snippet, insertText: "for ${1:item} in ${2:iterable}:\n    ${3:pass}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "For loop" },
    { label: "if/else", kind: CompletionItemKind.Snippet, insertText: "if ${1:condition}:\n    ${2:pass}\nelse:\n    ${3:pass}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "If/else block" },
    { label: "try/except", kind: CompletionItemKind.Snippet, insertText: "try:\n    ${1:pass}\nexcept ${2:Exception} as e:\n    ${3:pass}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Try/except block" },
    { label: "def function", kind: CompletionItemKind.Snippet, insertText: "def ${1:func_name}(${2:params}):\n    ${3:pass}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Define function" },
    { label: "class", kind: CompletionItemKind.Snippet, insertText: "class ${1:ClassName}:\n    def __init__(self${2:, params}):\n        ${3:pass}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Define class" },
    { label: "list comprehension", kind: CompletionItemKind.Snippet, insertText: "[${1:expr} for ${2:item} in ${3:iterable}]", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "List comprehension" },
    { label: "dict comprehension", kind: CompletionItemKind.Snippet, insertText: "{${1:key}: ${2:value} for ${3:item} in ${4:iterable}}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Dict comprehension" },
    { label: "with open", kind: CompletionItemKind.Snippet, insertText: "with open(${1:file}, '${2:r}') as f:\n    ${3:data = f.read()}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Open file with context manager" },
    { label: "lambda", kind: CompletionItemKind.Snippet, insertText: "lambda ${1:x}: ${2:x}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Lambda function" },
];

const javascriptCompletions: CompletionItem[] = [
    // Built-in functions & methods
    { label: "console.log", kind: CompletionItemKind.Function, insertText: "console.log(${1:value})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Log to console" },
    { label: "console.error", kind: CompletionItemKind.Function, insertText: "console.error(${1:value})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Log error to console" },
    { label: "JSON.parse", kind: CompletionItemKind.Function, insertText: "JSON.parse(${1:str})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Parse JSON string" },
    { label: "JSON.stringify", kind: CompletionItemKind.Function, insertText: "JSON.stringify(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Convert to JSON string" },
    { label: "Object.keys", kind: CompletionItemKind.Function, insertText: "Object.keys(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Get object keys" },
    { label: "Object.values", kind: CompletionItemKind.Function, insertText: "Object.values(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Get object values" },
    { label: "Object.entries", kind: CompletionItemKind.Function, insertText: "Object.entries(${1:obj})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Get object entries" },
    { label: "Array.isArray", kind: CompletionItemKind.Function, insertText: "Array.isArray(${1:value})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Check if value is array" },
    { label: "parseInt", kind: CompletionItemKind.Function, insertText: "parseInt(${1:str}, 10)", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Parse integer" },
    { label: "parseFloat", kind: CompletionItemKind.Function, insertText: "parseFloat(${1:str})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Parse float" },
    { label: "typeof", kind: CompletionItemKind.Keyword, insertText: "typeof ${1:value}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Get type of value" },
    { label: "Math.floor", kind: CompletionItemKind.Function, insertText: "Math.floor(${1:x})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Round down" },
    { label: "Math.ceil", kind: CompletionItemKind.Function, insertText: "Math.ceil(${1:x})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Round up" },
    { label: "Math.round", kind: CompletionItemKind.Function, insertText: "Math.round(${1:x})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Round to nearest integer" },
    { label: "Math.max", kind: CompletionItemKind.Function, insertText: "Math.max(${1:a}, ${2:b})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return maximum" },
    { label: "Math.min", kind: CompletionItemKind.Function, insertText: "Math.min(${1:a}, ${2:b})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Return minimum" },
    { label: "Promise.all", kind: CompletionItemKind.Function, insertText: "Promise.all([${1:promises}])", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Wait for all promises" },
    { label: "fetch", kind: CompletionItemKind.Function, insertText: "fetch(${1:url})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Fetch resource" },
    { label: "setTimeout", kind: CompletionItemKind.Function, insertText: "setTimeout(() => {\n    ${1:}\n}, ${2:1000})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Set timeout" },
    // Snippets
    { label: "arrow function", kind: CompletionItemKind.Snippet, insertText: "const ${1:name} = (${2:params}) => {\n    ${3:}\n};", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Arrow function" },
    { label: "async function", kind: CompletionItemKind.Snippet, insertText: "async function ${1:name}(${2:params}) {\n    ${3:}\n}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Async function" },
    { label: "try/catch", kind: CompletionItemKind.Snippet, insertText: "try {\n    ${1:}\n} catch (error) {\n    ${2:console.error(error);}\n}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Try/catch block" },
    { label: "for of", kind: CompletionItemKind.Snippet, insertText: "for (const ${1:item} of ${2:iterable}) {\n    ${3:}\n}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "For...of loop" },
    { label: "for in", kind: CompletionItemKind.Snippet, insertText: "for (const ${1:key} in ${2:obj}) {\n    ${3:}\n}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "For...in loop" },
    { label: "if/else", kind: CompletionItemKind.Snippet, insertText: "if (${1:condition}) {\n    ${2:}\n} else {\n    ${3:}\n}", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "If/else block" },
    { label: "map", kind: CompletionItemKind.Snippet, insertText: ".map((${1:item}) => ${2:item})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Array map" },
    { label: "filter", kind: CompletionItemKind.Snippet, insertText: ".filter((${1:item}) => ${2:condition})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Array filter" },
    { label: "reduce", kind: CompletionItemKind.Snippet, insertText: ".reduce((${1:acc}, ${2:item}) => {\n    ${3:}\n    return acc;\n}, ${4:{}})", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Array reduce" },
    { label: "destructure object", kind: CompletionItemKind.Snippet, insertText: "const { ${1:prop} } = ${2:obj};", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Object destructuring" },
    { label: "destructure array", kind: CompletionItemKind.Snippet, insertText: "const [${1:first}, ${2:second}] = ${3:arr};", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Array destructuring" },
    { label: "template literal", kind: CompletionItemKind.Snippet, insertText: "`${1:text} \\${${2:expr}}`", insertTextRules: InsertTextRule.InsertAsSnippet, detail: "Template literal string" },
];

export interface LanguageCompletions {
    python: CompletionItem[];
    javascript: CompletionItem[];
}

export const completionsByLanguage: LanguageCompletions = {
    python: [...kaiFusionCompletions, ...pythonCompletions],
    javascript: [...kaiFusionCompletions, ...javascriptCompletions],
};
