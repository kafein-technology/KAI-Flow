import { Field, Form, Formik, useFormikContext } from "formik";
import { Check, ChevronDown, Loader2, Plus, RefreshCw, Search, Settings, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import TabNavigation from "../../common/TabNavigation";
import { NodeCredentialSelect } from "../fields";
import { FieldLabel } from "../fields/FieldLabel";
import type { GenericData, NodeProperty } from "../types";
import {
  getMySQLColumns,
  getMySQLSchemas,
  getMySQLTables,
  type MySQLColumnInfo,
  type MySQLSchemaInfo,
  type MySQLTableInfo,
} from "~/services/mysqlService";

interface MySQLNodeFormProps {
  configData?: any;
  onSave?: (values: any) => void;
  onCancel: () => void;
  onChange?: (values: GenericData) => void;
}

const TABLE_OPERATIONS = ["delete_table", "insert", "upsert", "select", "update"];
const MAPPED_OPERATIONS = ["insert", "upsert", "update"];

const operationOptions = [
  { label: "Execute Query", value: "execute_query" },
  { label: "Select", value: "select" },
  { label: "Insert", value: "insert" },
  { label: "Update", value: "update" },
  { label: "Insert or Update", value: "upsert" },
  { label: "Delete", value: "delete_table" },
];

const sortDirectionOptions = [
  { label: "Ascending", value: "ASC" },
  { label: "Descending", value: "DESC" },
];

const deleteCommandOptions = [
  { label: "Truncate", value: "truncate" },
  { label: "Delete rows", value: "delete" },
  { label: "Drop table", value: "drop" },
];

const dataModeOptions = [
  { label: "Map Each Column Manually", value: "manual" },
  { label: "Map Incoming Data Automatically", value: "auto_map" },
];

const combineConditionOptions = [
  { label: "AND", value: "AND" },
  { label: "OR", value: "OR" },
];

const largeNumbersOptions = [
  { label: "Text", value: "text" },
  { label: "Numbers", value: "numbers" },
];

const priorityOptions = [
  { label: "Default", value: "none" },
  { label: "Low Priority", value: "LOW_PRIORITY" },
  { label: "High Priority", value: "HIGH_PRIORITY" },
];

const queryBatchingOptions = [
  { label: "Single Query", value: "single" },
  { label: "Independent", value: "independent" },
  { label: "Transaction", value: "transaction" },
];

const filterOptions = [
  { label: "is equal to", value: "=" },
  { label: "is not equal to", value: "!=" },
  { label: "is greater than", value: ">" },
  { label: "is greater than or equal to", value: ">=" },
  { label: "is less than", value: "<" },
  { label: "is less than or equal to", value: "<=" },
  { label: "contains", value: "contains" },
  { label: "contains (case sensitive)", value: "contains_case_sensitive" },
  { label: "is empty", value: "IS NULL" },
  { label: "is not empty", value: "IS NOT NULL" },
];

const inputClass =
  "w-full rounded-md border border-slate-600 bg-[#10182c] px-3 py-2.5 text-sm text-white outline-none transition focus:border-blue-500";

const parseValues = (value: unknown): Record<string, any> => {
  if (value && typeof value === "object" && !Array.isArray(value)) return value as Record<string, any>;
  try {
    const parsed = JSON.parse(String(value || "{}"));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
};

const parseRules = (value: unknown): Record<string, any>[] => {
  if (Array.isArray(value)) return value.filter((item) => item && typeof item === "object");
  try {
    const parsed = JSON.parse(String(value || "[]"));
    return Array.isArray(parsed) ? parsed.filter((item) => item && typeof item === "object") : [];
  } catch {
    return [];
  }
};

const parseSelectedColumns = (value: unknown) => {
  const raw = String(value || "*").trim();
  return raw === "*" ? [] : raw.split(",").map((column) => column.trim()).filter(Boolean);
};

const prepareValues = (values: Record<string, any>) => {
  const {
    mysql_column_values,
    mysql_selected_columns,
    mysql_sort_column,
    mysql_sort_direction,
    mysql_filter_column,
    mysql_filter_operator,
    mysql_filter_value,
    ...persistedValues
  } = values;
  const filterOperator = mysql_filter_operator || "=";
  const filterValue = filterOperator === "contains" || filterOperator === "contains_case_sensitive"
    ? `%${mysql_filter_value ?? ""}%`
    : mysql_filter_value;
  return {
    ...persistedValues,
    values: JSON.stringify(mysql_column_values || {}),
    output_columns: mysql_selected_columns?.length ? mysql_selected_columns.join(", ") : "*",
    sort: mysql_sort_column
      ? JSON.stringify([{ column: mysql_sort_column, direction: mysql_sort_direction || "ASC" }])
      : "[]",
    where: mysql_filter_column
      ? JSON.stringify([{
          column: mysql_filter_column,
          condition: filterOperator === "contains"
            ? "LIKE"
            : filterOperator === "contains_case_sensitive"
              ? "LIKE BINARY"
              : filterOperator,
          value: filterValue,
        }])
      : persistedValues.where || "[]",
  };
};

function Label({ children, help }: { children: React.ReactNode; help?: string }) {
  return <FieldLabel label={children} helpText={help} className="mb-2 text-sm font-medium text-slate-100" />;
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-slate-600 bg-slate-800/50 px-4 py-3">{children}</div>;
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 rounded-full transition-colors ${checked ? "bg-blue-500" : "bg-slate-600"}`}
    >
      <span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition-all ${checked ? "left-6" : "left-1"}`} />
    </button>
  );
}

function SearchableSelect({
  value,
  options,
  placeholder,
  loading,
  onChange,
  onRefresh,
}: {
  value: string;
  options: string[];
  placeholder: string;
  loading?: boolean;
  onChange: (value: string) => void;
  onRefresh?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const wrapper = useRef<HTMLDivElement>(null);
  const filtered = options.filter((option) => option.toLowerCase().includes(search.toLowerCase())).slice(0, 100);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (wrapper.current && !wrapper.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  return (
    <div ref={wrapper} className="relative flex gap-2">
      <div className="relative min-w-0 flex-1">
        <input
          value={open ? search : value}
          onFocus={() => { setSearch(value); setOpen(true); }}
          onChange={(event) => { setSearch(event.target.value); onChange(event.target.value); setOpen(true); }}
          placeholder={placeholder}
          className={`${inputClass} pr-9`}
        />
        <ChevronDown className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-slate-500" />
        {open && (
          <div className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-md border border-slate-700 bg-slate-900 shadow-xl">
            {loading ? (
              <div className="flex items-center gap-2 px-3 py-3 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Loading...</div>
            ) : filtered.length ? filtered.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => { onChange(option); setSearch(option); setOpen(false); }}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-blue-500/20 hover:text-blue-300 ${option === value ? "bg-blue-500/20 text-blue-300" : "text-slate-200"}`}
              >
                {option}{option === value && <Check className="h-4 w-4" />}
              </button>
            )) : (
              <div className="px-3 py-3 text-sm text-slate-400">Type a value manually</div>
            )}
          </div>
        )}
      </div>
      {onRefresh && (
        <button type="button" onClick={onRefresh} className="rounded-md border border-slate-600 px-3 text-slate-300 hover:border-blue-500 hover:text-blue-300" title="Refresh">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      )}
    </div>
  );
}

function SimpleSelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { label: string; value: string }[];
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (wrapper.current && !wrapper.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const current = options.find((option) => option.value === value);

  return (
    <div ref={wrapper} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`${inputClass} flex items-center justify-between text-left`}
      >
        <span>{current?.label ?? "Select..."}</span>
        <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-md border border-slate-700 bg-slate-900 shadow-xl">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => { onChange(option.value); setOpen(false); }}
              className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-blue-500/20 hover:text-blue-300 ${option.value === value ? "bg-blue-500/20 text-blue-300" : "text-slate-200"}`}
            >
              {option.label}{option.value === value && <Check className="h-4 w-4" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function MultiSearchableSelect({
  values,
  options,
  loading,
  onChange,
  onRefresh,
}: {
  values: string[];
  options: string[];
  loading?: boolean;
  onChange: (values: string[]) => void;
  onRefresh?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const wrapper = useRef<HTMLDivElement>(null);
  const filtered = options.filter((option) => option.toLowerCase().includes(search.toLowerCase()));

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (wrapper.current && !wrapper.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const toggle = (option: string) => onChange(values.includes(option) ? values.filter((item) => item !== option) : [...values, option]);

  return (
    <div ref={wrapper} className="relative flex gap-2">
      <div className="min-w-0 flex-1">
        <div className={`${inputClass} flex min-h-[42px] flex-wrap items-center gap-1.5 py-1.5`} onClick={() => setOpen(true)}>
          {values.map((value) => (
            <span key={value} className="flex items-center gap-1 rounded bg-blue-500/20 px-2 py-1 text-xs text-blue-300">
              {value}
              <button type="button" onClick={(event) => { event.stopPropagation(); toggle(value); }}><X className="h-3 w-3" /></button>
            </span>
          ))}
          <input
            value={search}
            onFocus={() => setOpen(true)}
            onChange={(event) => { setSearch(event.target.value); setOpen(true); }}
            placeholder={values.length ? "" : "All columns"}
            className="min-w-[100px] flex-1 bg-transparent py-1 text-sm outline-none"
          />
          <ChevronDown className="h-4 w-4 text-slate-500" />
        </div>
        {open && (
          <div className="absolute z-50 mt-1 max-h-56 w-[calc(100%-3.25rem)] overflow-auto rounded-md border border-slate-700 bg-slate-900 shadow-xl">
            {loading ? (
              <div className="flex items-center gap-2 px-3 py-3 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Loading...</div>
            ) : filtered.map((option) => (
              <button key={option} type="button" onClick={() => toggle(option)} className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-blue-500/20 hover:text-blue-300 ${values.includes(option) ? "bg-blue-500/20 text-blue-300" : "text-slate-200"}`}>
                {option}{values.includes(option) && <Check className="h-4 w-4" />}
              </button>
            ))}
          </div>
        )}
      </div>
      {onRefresh && (
        <button type="button" onClick={onRefresh} className="rounded-md border border-slate-600 px-3 text-slate-300 hover:border-blue-500 hover:text-blue-300" title="Refresh">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      )}
    </div>
  );
}

function ColumnValues({ columns, operation }: { columns: MySQLColumnInfo[]; operation: string }) {
  const { values, setFieldValue } = useFormikContext<Record<string, any>>();
  const mapped = values.mysql_column_values || {};
  const visibleColumns = columns.filter((column) => column.name !== values.match_column || operation === "insert");

  if (!visibleColumns.length) {
    return (
      <Card>
        <Label help="Table metadata could not be loaded, so provide the column values as a JSON object.">Values to Send</Label>
        <textarea rows={6} className={inputClass} value={JSON.stringify(mapped, null, 2)} onChange={(event) => {
          try { setFieldValue("mysql_column_values", JSON.parse(event.target.value)); } catch { /* Keep the last valid JSON. */ }
        }} />
      </Card>
    );
  }

  return (
    <Card>
      <Label help="Value written to each column. The fields come from the selected MySQL table.">Values to Send</Label>
      <div className="space-y-3">
        {visibleColumns.map((column) => {
          const required = !column.nullable && column.default == null && !column.extra.toLowerCase().includes("auto_increment");
          const booleanType = ["bool", "boolean", "tinyint(1)"].some((type) => column.column_type.toLowerCase() === type);
          const numericType = /^(tinyint|smallint|mediumint|int|bigint|decimal|numeric|float|double)/.test(column.data_type);
          const dateType = /^(date|datetime|timestamp|time|year)/.test(column.data_type);
          const current = mapped[column.name];
          return (
            <div key={column.name} className="border-l-2 border-slate-600 pl-3">
              <div className="mb-1 flex justify-between text-xs">
                <span className="text-slate-200">{column.name}{required && <span className="ml-1 text-amber-400">required</span>}</span>
                <span className="text-slate-500">{column.column_type}</span>
              </div>
              {booleanType ? (
                <Toggle checked={Boolean(current)} onChange={(checked) => setFieldValue(`mysql_column_values.${column.name}`, checked)} />
              ) : (
                <input type={numericType ? "number" : dateType ? "datetime-local" : "text"} value={current ?? ""} placeholder={column.default != null ? `Default: ${column.default}` : ""} onChange={(event) => {
                  const raw = event.target.value;
                  setFieldValue(`mysql_column_values.${column.name}`, numericType && raw !== "" ? Number(raw) : raw);
                }} className={inputClass} />
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function MySQLFields({ activeTab, onChange, onOpenAdvanced }: { activeTab: string; onChange?: (values: GenericData) => void; onOpenAdvanced: () => void }) {
  const { values, setFieldValue, initialValues } = useFormikContext<Record<string, any>>();
  const [schemas, setSchemas] = useState<MySQLSchemaInfo[]>([]);
  const [tables, setTables] = useState<MySQLTableInfo[]>([]);
  const [columns, setColumns] = useState<MySQLColumnInfo[]>([]);
  const [loadingSchemas, setLoadingSchemas] = useState(false);
  const [loadingTables, setLoadingTables] = useState(false);
  const [loadingColumns, setLoadingColumns] = useState(false);
  const changeRef = useRef(onChange);
  const firstChange = useRef(true);
  changeRef.current = onChange;

  const loadSchemas = useCallback(async () => {
    if (!values.credential_id) { setSchemas([]); return; }
    setLoadingSchemas(true);
    try { setSchemas(await getMySQLSchemas(values.credential_id)); } catch { setSchemas([]); }
    finally { setLoadingSchemas(false); }
  }, [values.credential_id]);

  const loadTables = useCallback(async () => {
    if (!values.credential_id) { setTables([]); return; }
    setLoadingTables(true);
    try { setTables(await getMySQLTables(values.credential_id, values.schema || "")); } catch { setTables([]); }
    finally { setLoadingTables(false); }
  }, [values.credential_id, values.schema]);

  const loadColumns = useCallback(async () => {
    if (!values.credential_id || !values.table || !TABLE_OPERATIONS.includes(values.operation)) { setColumns([]); return; }
    setLoadingColumns(true);
    try { setColumns(await getMySQLColumns(values.credential_id, values.table, values.schema || "")); } catch { setColumns([]); }
    finally { setLoadingColumns(false); }
  }, [values.credential_id, values.schema, values.table, values.operation]);

  useEffect(() => { void loadSchemas(); }, [loadSchemas]);
  useEffect(() => { void loadTables(); }, [loadTables]);
  useEffect(() => { void loadColumns(); }, [loadColumns]);
  useEffect(() => {
    // Preselect the credential's own database the way the schema list orders it.
    if (!values.schema && schemas.length) setFieldValue("schema", schemas[0].name);
  }, [schemas, values.schema, setFieldValue]);
  useEffect(() => {
    if (firstChange.current) { firstChange.current = false; return; }
    if (JSON.stringify(values) !== JSON.stringify(initialValues)) changeRef.current?.(prepareValues(values));
  }, [values, initialValues]);

  if (activeTab === "advanced") {
    return (
      <div className="grid grid-cols-1 gap-3 p-6">
        {values.operation === "select" && <Card><Label help="Drop duplicate rows from the result set.">Select Distinct</Label><Toggle checked={Boolean(values.select_distinct)} onChange={(checked) => setFieldValue("select_distinct", checked)} /></Card>}
        {["insert", "upsert", "update", "execute_query"].includes(values.operation) && <Card><Label help="Send empty text values to MySQL as NULL instead of an empty string.">Replace Empty Strings with NULL</Label><Toggle checked={Boolean(values.replace_empty_strings)} onChange={(checked) => setFieldValue("replace_empty_strings", checked)} /></Card>}
        {["select", "execute_query"].includes(values.operation) && <Card><Label help="Return values above the safe integer range as text or as numbers.">Output Large Numbers As</Label><SimpleSelect value={values.large_numbers_output || "text"} options={largeNumbersOptions} onChange={(value) => setFieldValue("large_numbers_output", value)} /></Card>}
        {["select", "execute_query"].includes(values.operation) && <Card><Label help="Return DECIMAL columns as numbers instead of strings.">Output Decimals as Numbers</Label><Toggle checked={Boolean(values.decimal_numbers)} onChange={(checked) => setFieldValue("decimal_numbers", checked)} /></Card>}
        {values.operation === "insert" && <Card><Label help="MySQL INSERT priority hint used while the table is busy.">Insert Priority</Label><SimpleSelect value={values.priority || "none"} options={priorityOptions} onChange={(value) => setFieldValue("priority", value)} /></Card>}
        {values.operation === "insert" && <Card><Label help="Ignore rows that break a unique constraint instead of failing the node.">Skip on Conflict</Label><Toggle checked={Boolean(values.skip_on_conflict)} onChange={(checked) => setFieldValue("skip_on_conflict", checked)} /></Card>}
        <Card><Label help="Single query sends one statement, independent runs each row on its own, transaction wraps them together.">Query Batching</Label><SimpleSelect value={values.query_batching || "single"} options={queryBatchingOptions} onChange={(value) => setFieldValue("query_batching", value)} /></Card>
        <Card><Label help="Time reserved for opening the MySQL connection.">Connection Timeout (ms)</Label><Field type="number" name="connection_timeout_ms" className={inputClass} /></Card>
        <Card><Label help="Maximum number of connections this node opens at the same time.">Connections Limit</Label><Field type="number" name="connection_limit" className={inputClass} /></Card>
        <Card><Label help="Add the executed SQL and per-query metadata to the node output.">Output Query Execution Details</Label><Toggle checked={Boolean(values.detailed_output)} onChange={(checked) => setFieldValue("detailed_output", checked)} /></Card>
        <Card><Label help="Report the error in the output and keep the workflow running instead of stopping it.">Continue on Fail</Label><Toggle checked={Boolean(values.continue_on_fail)} onChange={(checked) => setFieldValue("continue_on_fail", checked)} /></Card>
      </div>
    );
  }

  const columnNames = columns.map((column) => column.name);
  const selectedColumns: string[] = values.mysql_selected_columns || [];
  const filterDoesNotNeedValue = ["IS NULL", "IS NOT NULL"].includes(values.mysql_filter_operator);
  const hasCredential = Boolean(values.credential_id);
  const listHint = "Select credential to see the list. A name can still be typed.";
  const hasTable = Boolean(values.table);

  const resetTableDependentFields = () => {
    setFieldValue("mysql_selected_columns", []);
    setFieldValue("mysql_sort_column", "");
    setFieldValue("mysql_sort_direction", "ASC");
    setFieldValue("mysql_filter_column", "");
    setFieldValue("mysql_filter_operator", "=");
    setFieldValue("mysql_filter_value", "");
    setFieldValue("mysql_column_values", {});
    setFieldValue("match_column", "");
  };

  const resetTable = () => {
    setFieldValue("table", "");
    resetTableDependentFields();
  };

  return (
    <div className="grid grid-cols-1 gap-3 p-6">
      <Card>
        <NodeCredentialSelect property={{ name: "credential_id", displayName: "Credential", type: "credential-select", serviceType: "mysql", required: true } as NodeProperty} values={values} setFieldValue={setFieldValue} />
      </Card>
      <Card><Label help="Database action this node runs. Every other field adapts to the operation you pick.">Operation</Label><SimpleSelect value={values.operation || ""} options={operationOptions} onChange={(value) => setFieldValue("operation", value)} /></Card>

      {TABLE_OPERATIONS.includes(values.operation) && (
        <Card>
          <Label help="Database that holds the table. Defaults to the database defined by the selected credential.">Schema</Label>
          <SearchableSelect
            value={values.schema || ""}
            options={schemas.map((schema) => schema.name)}
            placeholder="Select or type a schema"
            loading={loadingSchemas}
            onChange={(value) => { setFieldValue("schema", value); resetTable(); }}
            onRefresh={loadSchemas}
          />
          <p className="mt-1 text-xs text-slate-500">{hasCredential ? `${schemas.length} available` : listHint}</p>
        </Card>
      )}
      {TABLE_OPERATIONS.includes(values.operation) && (
        <Card>
          <Label help="Table the operation runs against. Pick one from the list or type a name manually.">Table</Label>
          <SearchableSelect value={values.table || ""} options={tables.map((table) => table.name)} placeholder="Select or type a table" loading={loadingTables} onChange={(value) => { setFieldValue("table", value); resetTableDependentFields(); }} onRefresh={loadTables} />
          <p className="mt-1 text-xs text-slate-500">{hasCredential ? `${tables.length} available` : listHint}</p>
        </Card>
      )}

      {values.operation === "select" && values.table && (
        <>
          <Card>
            <Label help="Columns returned by the query. Leave it empty to return every column of the table.">Columns</Label>
            <MultiSearchableSelect values={selectedColumns} options={columnNames} loading={loadingColumns} onChange={(next) => setFieldValue("mysql_selected_columns", next)} onRefresh={loadColumns} />
            <p className="mt-1 text-xs text-slate-500">{selectedColumns.length ? `${selectedColumns.length} of ${columnNames.length} selected` : `All ${columnNames.length} columns`}</p>
          </Card>
          <Card><div className="flex items-center justify-between"><Label help="Return every matching row instead of stopping at the row limit.">Return All</Label><Toggle checked={Boolean(values.return_all)} onChange={(checked) => setFieldValue("return_all", checked)} /></div></Card>
          {!values.return_all && <Card><Label help="Maximum number of rows returned while Return All is off.">Limit</Label><Field type="number" min="1" name="limit" className={inputClass} /></Card>}
          <Card>
            <Label help="Column used to order the returned rows. Leave it empty to keep the database order.">Sort Column</Label>
            <SearchableSelect value={values.mysql_sort_column || ""} options={columnNames} placeholder="No ordering" loading={loadingColumns} onChange={(value) => setFieldValue("mysql_sort_column", value)} onRefresh={loadColumns} />
            <p className="mt-1 text-xs text-slate-500">{columnNames.length} available</p>
          </Card>
          {values.mysql_sort_column && <Card><Label help="Ascending sorts from the smallest value upwards, descending does the opposite.">Sort Direction</Label><SimpleSelect value={values.mysql_sort_direction || "ASC"} options={sortDirectionOptions} onChange={(value) => setFieldValue("mysql_sort_direction", value)} /></Card>}
          <Card>
            <Label help="Column the filter is applied to. Leave it empty to match every row.">Filter Column</Label>
            <SearchableSelect value={values.mysql_filter_column || ""} options={columnNames} placeholder="No filter, match every row" loading={loadingColumns} onChange={(value) => setFieldValue("mysql_filter_column", value)} onRefresh={loadColumns} />
            <p className="mt-1 text-xs text-slate-500">{columnNames.length} available</p>
          </Card>
          {values.mysql_filter_column && <Card><Label help="How the filter value is compared with the column value.">Filter Operator</Label><SimpleSelect value={values.mysql_filter_operator || "="} options={filterOptions} onChange={(value) => setFieldValue("mysql_filter_operator", value)} /></Card>}
          {values.mysql_filter_column && !filterDoesNotNeedValue && <Card><Label help="Value the filter compares against. Not used by the is empty checks.">Filter Value</Label><Field name="mysql_filter_value" className={inputClass} placeholder="e.g. Istanbul" /></Card>}
        </>
      )}

      {values.operation === "delete_table" && hasTable && <Card><Label help="Truncate empties the table, Delete rows removes only filtered rows, Drop removes the table itself.">Command</Label><SimpleSelect value={values.delete_command || "truncate"} options={deleteCommandOptions} onChange={(value) => setFieldValue("delete_command", value)} /></Card>}
      {values.operation === "execute_query" && <Card><Label help="SQL statement to run. Use $1, $2 placeholders for the query parameters below.">SQL Query</Label><Field as="textarea" rows={8} name="query" className={inputClass} placeholder="SELECT * FROM customers WHERE status = $1" /></Card>}
      {values.operation === "execute_query" && <Card><Label help="JSON array of values bound to the $1, $2 placeholders in the query.">Query Parameters</Label><Field as="textarea" rows={5} name="query_parameters" className={inputClass} placeholder="[]" /></Card>}

      {MAPPED_OPERATIONS.includes(values.operation) && hasTable && <Card><Label help="Write the column values yourself or map them automatically from the incoming data.">Mapping Column Mode</Label><SimpleSelect value={values.data_mode || "manual"} options={dataModeOptions} onChange={(value) => setFieldValue("data_mode", value)} /></Card>}
      {["upsert", "update"].includes(values.operation) && hasTable && <Card><Label help="Column used to find the existing row that will be updated.">Columns to Match On</Label><SearchableSelect value={values.match_column || ""} options={columnNames} placeholder={loadingColumns ? "Loading columns..." : "Select or type a column"} loading={loadingColumns} onChange={(value) => setFieldValue("match_column", value)} onRefresh={loadColumns} /></Card>}
      {["upsert", "update"].includes(values.operation) && hasTable && values.data_mode === "manual" && <Card><Label help="Value searched in the match column when you map the values manually.">Value of Column to Match On</Label><Field name="match_value" className={inputClass} /></Card>}
      {MAPPED_OPERATIONS.includes(values.operation) && hasTable && values.data_mode === "manual" && <ColumnValues columns={columns} operation={values.operation} />}

      {values.operation === "delete_table" && hasTable && values.delete_command === "delete" && <Card><Label help="JSON conditions that decide which rows are deleted.">Select Rows</Label><Field as="textarea" rows={5} name="where" className={inputClass} placeholder='[{"column":"status","condition":"=","value":"active"}]' /></Card>}
      {values.operation === "delete_table" && hasTable && <Card><Label help="AND requires every condition to match, OR accepts any of them.">Combine Conditions</Label><SimpleSelect value={values.combine_conditions || "AND"} options={combineConditionOptions} onChange={(value) => setFieldValue("combine_conditions", value)} /></Card>}

      <button type="button" onClick={onOpenAdvanced} className="flex w-full items-center justify-between rounded-lg border border-dashed border-slate-500 px-4 py-3 text-sm text-slate-200 hover:border-blue-500 hover:text-blue-300">
        <span className="flex items-center gap-2"><Plus className="h-4 w-4" />Add Option</span><ChevronDown className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function MySQLNodeForm({ configData, onSave, onCancel, onChange }: MySQLNodeFormProps) {
  const properties = configData?.metadata?.properties || [];
  const initialValues = useMemo(() => {
    const sortRule = parseRules(configData?.sort)[0] || {};
    const filterRule = parseRules(configData?.where)[0] || {};
    const rawFilterValue = filterRule.value;
    const isContains = ["LIKE", "LIKE BINARY"].includes(filterRule.condition) && typeof rawFilterValue === "string" && rawFilterValue.startsWith("%") && rawFilterValue.endsWith("%");
    return {
      ...properties.reduce((acc: Record<string, any>, property: NodeProperty) => {
        acc[property.name] = property.default ?? (property.type === "checkbox" ? false : "");
        return acc;
      }, {}),
      ...configData,
      mysql_column_values: parseValues(configData?.values),
      mysql_selected_columns: parseSelectedColumns(configData?.output_columns),
      mysql_sort_column: sortRule.column || "",
      mysql_sort_direction: sortRule.direction || "ASC",
      mysql_filter_column: filterRule.column || "",
      mysql_filter_operator: isContains
        ? filterRule.condition === "LIKE BINARY" ? "contains_case_sensitive" : "contains"
        : filterRule.condition || filterRule.operator || "=",
      mysql_filter_value: isContains ? rawFilterValue.slice(1, -1) : rawFilterValue ?? "",
    };
  }, [configData, properties]);
  const [activeTab, setActiveTab] = useState("basic");
  const tabs = [
    { id: "basic", label: "Basic", icon: Settings },
    { id: "advanced", label: "Advanced", icon: Settings },
  ];

  return (
    <div className="h-full w-full">
      <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} className="mb-4" />
      <Formik initialValues={initialValues} enableReinitialize onSubmit={(values) => onSave?.(prepareValues(values))}>
        <Form>
          <MySQLFields activeTab={activeTab} onChange={onChange} onOpenAdvanced={() => setActiveTab("advanced")} />
          <div className="hidden"><button type="submit">Save</button><button type="button" onClick={onCancel}>Cancel</button></div>
        </Form>
      </Formik>
    </div>
  );
}
