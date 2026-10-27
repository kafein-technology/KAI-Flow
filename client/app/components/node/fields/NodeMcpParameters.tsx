import { useEffect, useRef, useState } from "react";
import { useFormikContext } from "formik";
import type { NodeProperty } from "../types";
import { apiClient } from "~/lib/api-client";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

type Schema = {
  type?: string | string[];
  title?: string;
  description?: string;
  properties?: Record<string, Schema>;
  required?: string[];
  enum?: unknown[];
  default?: unknown;
  [key: string]: unknown;
};

function ParameterValue({ name, schema, value, onChange }: {
  name: string;
  schema: Schema;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const type = Array.isArray(schema.type) ? schema.type.find((entry) => entry !== "null") : schema.type;
  const complex = type === "object" || type === "array" || (!type && !schema.enum);
  const current = value === undefined ? schema.default : value;

  useEffect(() => {
    if (complex) setDraft(JSON.stringify(current ?? (type === "array" ? [] : {}), null, 2));
  }, [name, complex, current, type]);

  if (schema.enum?.length) {
    const selectedIndex = schema.enum.findIndex((option) => JSON.stringify(option) === JSON.stringify(current));
    return (
      <select aria-label={name} value={selectedIndex < 0 ? "" : String(selectedIndex)}
        onChange={(event) => onChange(event.target.value === "" ? undefined : schema.enum![Number(event.target.value)])}
        className="kai-node-field-control px-3 py-2">
        <option value="">Select a value</option>
        {schema.enum.map((option, index) => <option key={index} value={index}>{String(option)}</option>)}
      </select>
    );
  }
  if (type === "boolean") {
    return <input aria-label={name} type="checkbox" checked={Boolean(current)} onChange={(event) => onChange(event.target.checked)} />;
  }
  if (complex) {
    return <>
      <textarea aria-label={name} rows={4} value={draft} className="kai-node-field-control px-3 py-2 font-mono text-xs"
        onChange={(event) => { setDraft(event.target.value); setError(""); }}
        onBlur={() => {
          try { onChange(JSON.parse(draft)); setError(""); }
          catch { setError("Enter valid JSON before saving this parameter."); }
        }} />
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </>;
  }
  return <input aria-label={name} type={type === "number" || type === "integer" ? "number" : "text"}
    step={type === "integer" ? 1 : "any"}
    value={current === undefined || current === null ? "" : String(current)}
    onChange={(event) => onChange(type === "number" || type === "integer"
      ? event.target.value === "" ? undefined : Number(event.target.value)
      : event.target.value)}
    className="kai-node-field-control px-3 py-2" />;
}

export function NodeMcpParameters({ property, values, nodeType }: {
  property: NodeProperty;
  values: Record<string, unknown>;
  nodeType?: string;
}) {
  const { setFieldValue } = useFormikContext<Record<string, unknown>>();
  const [schema, setSchema] = useState<Schema | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const tool = String(values.tool || "");
  const previousTool = useRef(tool);
  const latestValues = useRef(values);
  latestValues.current = values;
  const dependencyKey = JSON.stringify([tool, values.endpoint_url, values.transport, values.credential_id]);

  useEffect(() => {
    if (previousTool.current !== tool) {
      previousTool.current = tool;
      latestValues.current = { ...latestValues.current, [property.name]: "{}" };
      setSchema(null);
      void setFieldValue(property.name, "{}");
    }
  }, [tool, property.name, setFieldValue]);

  useEffect(() => {
    if (!nodeType || !tool || !values.endpoint_url) { setSchema(null); setError(""); return; }
    let cancelled = false;
    setLoading(true);
    setError("");
    void apiClient.post<{ options: Schema }>(`/nodes/${nodeType}/options`, {
      property_name: property.name,
      values: { tool, endpoint_url: values.endpoint_url, transport: values.transport,
        credential_id: values.credential_id },
    }).then((response) => {
      if (cancelled) return;
      setSchema(response.options);
      let current: Record<string, unknown> = {};
      try {
        const parsed = JSON.parse(String(latestValues.current[property.name] || "{}"));
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) current = parsed;
      } catch { /* Invalid input can be repaired in JSON mode. */ }
      const next = { ...current };
      for (const [name, definition] of Object.entries(response.options.properties || {})) {
        if (next[name] === undefined && definition.default !== undefined) next[name] = definition.default;
      }
      if (JSON.stringify(next) !== JSON.stringify(current)) void setFieldValue(property.name, JSON.stringify(next));
    }).catch((reason) => {
      if (!cancelled) { setSchema(null); setError(reason instanceof Error ? reason.message : "Could not load tool parameters"); }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [dependencyKey, nodeType, property.name]);

  let parameters: Record<string, unknown> = {};
  try {
    const raw = values[property.name];
    const parsed = typeof raw === "string" ? JSON.parse(raw || "{}") : raw;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) parameters = parsed as Record<string, unknown>;
  } catch { /* The user can repair the JSON in JSON mode. */ }

  const update = (name: string, value: unknown) => {
    const next = { ...parameters };
    if (value === undefined) delete next[name];
    else next[name] = value;
    void setFieldValue(property.name, JSON.stringify(next));
  };

  return <div className="col-span-2">
    <FieldLabel label={property.displayName} helpText={getFieldHelpText(property)} />
    {!tool && <p className="text-xs text-[var(--kai-text-muted)]">Select an MCP tool to load its parameters.</p>}
    {loading && <p className="text-xs text-[var(--kai-text-muted)]">Loading tool parameters...</p>}
    {error && <p className="text-xs text-red-400">{error}</p>}
    {schema && !loading && (
      Object.keys(schema.properties || {}).length === 0
        ? <p className="text-xs text-[var(--kai-text-muted)]">This tool has no named parameters. Use JSON mode for custom input.</p>
        : <div className="space-y-3">{Object.entries(schema.properties || {}).map(([name, definition]) => (
          <div key={name}>
            <label className="mb-1 block text-sm text-[var(--kai-text)]">
              {definition.title || name}{schema.required?.includes(name) && <span className="ml-1 text-red-400">*</span>}
            </label>
            <ParameterValue name={name} schema={definition} value={parameters[name]}
              onChange={(value) => update(name, value)} />
            {definition.description && <p className="mt-1 text-xs text-[var(--kai-text-muted)]">{definition.description}</p>}
          </div>
        ))}</div>
    )}
  </div>;
}
