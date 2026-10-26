export type VariableCompletion = { start: number; end: number; query: string };

const VARIABLE_REFERENCE = /\$\{\{\s*vars\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g;

export type VariablePreview = { value: string; missing: string[] };

export function resolveVariablePreview(
  template: string,
  values: ReadonlyMap<string, string>,
): VariablePreview | null {
  const references = [...template.matchAll(VARIABLE_REFERENCE)];
  if (references.length === 0) return null;

  // Other Jinja expressions need execution context, so a browser-only preview would be misleading.
  if (/\$\{\{|\{\{/.test(template.replace(VARIABLE_REFERENCE, ""))) return null;

  const missing = [...new Set(references.map((match) => match[1]).filter((name) => !values.has(name)))];
  if (missing.length > 0) return { value: "", missing };

  return {
    value: template.replace(VARIABLE_REFERENCE, (_, name: string) => values.get(name) ?? ""),
    missing: [],
  };
}

export function findVariableCompletion(value: string, caret: number): VariableCompletion | null {
  const before = value.slice(0, caret);
  const start = before.lastIndexOf("${{");
  if (start < 0) return null;

  const expression = before.slice(start + 3).trimStart();
  if (expression.includes("}}") || /[^A-Za-z0-9_.]/.test(expression)) return null;
  const query = "vars.".startsWith(expression) ? "" : expression.startsWith("vars.")
    ? expression.slice(5)
    : expression;
  if (query.includes(".")) return null;
  return { start, end: caret, query };
}
