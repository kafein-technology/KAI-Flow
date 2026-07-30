import { Field, Form, Formik, useFormikContext } from "formik";
import { Check, ChevronDown, Loader2, Plus, RefreshCw, Search, Settings, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import TabNavigation from "../../common/TabNavigation";
import { NodeCredentialSelect } from "../fields";
import type { GenericData, NodeProperty } from "../types";
import {
  getMySQLColumns,
  getMySQLTables,
  type MySQLColumnInfo,
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

const filterOptions = [
  { label: "Is equal to", value: "=" },
  { label: "Is not equal to", value: "!=" },
  { label: "Is greater than", value: ">" },
  { label: "Is greater than or equal to", value: ">=" },
  { label: "Is less than", value: "<" },
  { label: "Is less than or equal to", value: "<=" },
  { label: "Contains", value: "contains" },
  { label: "Contains (case sensitive)", value: "contains_case_sensitive" },
  { label: "Is empty", value: "IS NULL" },
  { label: "Is not empty", value: "IS NOT NULL" },
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

function Label({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="mb-2">
      <label className="text-sm font-medium text-slate-100">{children}</label>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
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
        <Label hint="Table metadata could not be loaded; provide a JSON object.">Values to Send</Label>
        <textarea rows={6} className={inputClass} value={JSON.stringify(mapped, null, 2)} onChange={(event) => {
          try { setFieldValue("mysql_column_values", JSON.parse(event.target.value)); } catch { /* Keep the last valid JSON. */ }
        }} />
      </Card>
    );
  }

  return (
    <Card>
      <Label hint="Fields come from the selected MySQL table.">Values to Send</Label>
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
  const [tables, setTables] = useState<MySQLTableInfo[]>([]);
  const [columns, setColumns] = useState<MySQLColumnInfo[]>([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [loadingColumns, setLoadingColumns] = useState(false);
  const changeRef = useRef(onChange);
  const firstChange = useRef(true);
  changeRef.current = onChange;

  const loadTables = useCallback(async () => {
    if (!values.credential_id) { setTables([]); return; }
    setLoadingTables(true);
    try { setTables(await getMySQLTables(values.credential_id)); } catch { setTables([]); }
    finally { setLoadingTables(false); }
  }, [values.credential_id]);

  const loadColumns = useCallback(async () => {
    if (!values.credential_id || !values.table || !TABLE_OPERATIONS.includes(values.operation)) { setColumns([]); return; }
    setLoadingColumns(true);
    try { setColumns(await getMySQLColumns(values.credential_id, values.table)); } catch { setColumns([]); }
    finally { setLoadingColumns(false); }
  }, [values.credential_id, values.table, values.operation]);

  useEffect(() => { void loadTables(); }, [loadTables]);
  useEffect(() => { void loadColumns(); }, [loadColumns]);
  useEffect(() => {
    if (firstChange.current) { firstChange.current = false; return; }
    if (JSON.stringify(values) !== JSON.stringify(initialValues)) changeRef.current?.(prepareValues(values));
  }, [values, initialValues]);

  if (activeTab === "advanced") {
    return (
      <div className="grid grid-cols-1 gap-3 p-6">
        {values.operation === "select" && <Card><Label>Select Distinct</Label><Toggle checked={Boolean(values.select_distinct)} onChange={(checked) => setFieldValue("select_distinct", checked)} /></Card>}
        {["insert", "upsert", "update", "execute_query"].includes(values.operation) && <Card><Label>Replace Empty Strings with NULL</Label><Toggle checked={Boolean(values.replace_empty_strings)} onChange={(checked) => setFieldValue("replace_empty_strings", checked)} /></Card>}
        {["select", "execute_query"].includes(values.operation) && <Card><Label>Output Large Numbers As</Label><Field as="select" name="large_numbers_output" className={inputClass}><option value="text">Text</option><option value="numbers">Numbers</option></Field></Card>}
        {["select", "execute_query"].includes(values.operation) && <Card><Label>Output Decimals as Numbers</Label><Toggle checked={Boolean(values.decimal_numbers)} onChange={(checked) => setFieldValue("decimal_numbers", checked)} /></Card>}
        {values.operation === "insert" && <Card><Label>Insert Priority</Label><Field as="select" name="priority" className={inputClass}><option value="none">Default</option><option value="LOW_PRIORITY">Low Priority</option><option value="HIGH_PRIORITY">High Priority</option></Field></Card>}
        {values.operation === "insert" && <Card><Label>Skip on Conflict</Label><Toggle checked={Boolean(values.skip_on_conflict)} onChange={(checked) => setFieldValue("skip_on_conflict", checked)} /></Card>}
        <Card><Label>Query Batching</Label><Field as="select" name="query_batching" className={inputClass}><option value="single">Single Query</option><option value="independent">Independent</option><option value="transaction">Transaction</option></Field></Card>
        <Card><Label>Connection Timeout (ms)</Label><Field type="number" name="connection_timeout_ms" className={inputClass} /></Card>
        <Card><Label>Connections Limit</Label><Field type="number" name="connection_limit" className={inputClass} /></Card>
        <Card><Label>Output Query Execution Details</Label><Toggle checked={Boolean(values.detailed_output)} onChange={(checked) => setFieldValue("detailed_output", checked)} /></Card>
        <Card><Label>Continue on Fail</Label><Toggle checked={Boolean(values.continue_on_fail)} onChange={(checked) => setFieldValue("continue_on_fail", checked)} /></Card>
      </div>
    );
  }

  const columnNames = columns.map((column) => column.name);
  const selectedColumns: string[] = values.mysql_selected_columns || [];
  const filterDoesNotNeedValue = ["IS NULL", "IS NOT NULL"].includes(values.mysql_filter_operator);

  return (
    <div className="grid grid-cols-1 gap-3 p-6">
      <Card>
        <NodeCredentialSelect property={{ name: "credential_id", displayName: "Credential", type: "credential-select", serviceType: "mysql", required: true } as NodeProperty} values={values} setFieldValue={setFieldValue} />
      </Card>
      <Card><Label>Operation</Label><Field as="select" name="operation" className={inputClass}>{operationOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Field></Card>

      {TABLE_OPERATIONS.includes(values.operation) && <Card><Label hint="The default database is defined by the selected credential.">Database</Label><div className={`${inputClass} cursor-not-allowed text-slate-400`}>Credential database</div></Card>}
      {TABLE_OPERATIONS.includes(values.operation) && (
        <Card>
          <Label>Table</Label>
          <SearchableSelect value={values.table || ""} options={tables.map((table) => table.name)} placeholder="Select or type a table" loading={loadingTables} onChange={(value) => setFieldValue("table", value)} onRefresh={loadTables} />
          <p className="mt-1 text-xs text-slate-500">{tables.length} available</p>
        </Card>
      )}

      {values.operation === "select" && (
        <>
          <Card>
            <Label>Columns</Label>
            <MultiSearchableSelect values={selectedColumns} options={columnNames} loading={loadingColumns} onChange={(next) => setFieldValue("mysql_selected_columns", next)} onRefresh={loadColumns} />
            <p className="mt-1 text-xs text-slate-500">{selectedColumns.length ? `${selectedColumns.length} of ${columnNames.length} selected` : `All ${columnNames.length} columns`}</p>
          </Card>
          <Card><div className="flex items-center justify-between"><Label>Return All</Label><Toggle checked={Boolean(values.return_all)} onChange={(checked) => setFieldValue("return_all", checked)} /></div></Card>
          {!values.return_all && <Card><Label>Limit</Label><Field type="number" min="1" name="limit" className={inputClass} /></Card>}
          <Card>
            <Label>Sort Column</Label>
            <SearchableSelect value={values.mysql_sort_column || ""} options={columnNames} placeholder="No ordering" loading={loadingColumns} onChange={(value) => setFieldValue("mysql_sort_column", value)} onRefresh={loadColumns} />
            <p className="mt-1 text-xs text-slate-500">{columnNames.length} available</p>
          </Card>
          {values.mysql_sort_column && <Card><Label>Sort Direction</Label><Field as="select" name="mysql_sort_direction" className={inputClass}><option value="ASC">Ascending</option><option value="DESC">Descending</option></Field></Card>}
          <Card>
            <Label>Filter Column</Label>
            <SearchableSelect value={values.mysql_filter_column || ""} options={columnNames} placeholder="No filter, match every row" loading={loadingColumns} onChange={(value) => setFieldValue("mysql_filter_column", value)} onRefresh={loadColumns} />
            <p className="mt-1 text-xs text-slate-500">{columnNames.length} available</p>
          </Card>
          {values.mysql_filter_column && <Card><Label>Filter Operator</Label><Field as="select" name="mysql_filter_operator" className={inputClass}>{filterOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Field></Card>}
          {values.mysql_filter_column && !filterDoesNotNeedValue && <Card><Label>Filter Value</Label><Field name="mysql_filter_value" className={inputClass} placeholder="e.g. Istanbul" /></Card>}
        </>
      )}

      {values.operation === "delete_table" && <Card><Label>Command</Label><Field as="select" name="delete_command" className={inputClass}><option value="truncate">Truncate</option><option value="delete">Delete rows</option><option value="drop">Drop table</option></Field></Card>}
      {values.operation === "execute_query" && <Card><Label>SQL Query</Label><Field as="textarea" rows={8} name="query" className={inputClass} placeholder="SELECT * FROM customers WHERE status = $1" /></Card>}
      {values.operation === "execute_query" && <Card><Label>Query Parameters</Label><Field as="textarea" rows={5} name="query_parameters" className={inputClass} placeholder="[]" /></Card>}

      {MAPPED_OPERATIONS.includes(values.operation) && <Card><Label hint="Write the column values yourself or map incoming data.">Mapping Column Mode</Label><Field as="select" name="data_mode" className={inputClass}><option value="manual">Map Each Column Manually</option><option value="auto_map">Map Incoming Data Automatically</option></Field></Card>}
      {["upsert", "update"].includes(values.operation) && <Card><Label>Columns to Match On</Label><SearchableSelect value={values.match_column || ""} options={columnNames} placeholder={loadingColumns ? "Loading columns..." : "Select or type a column"} loading={loadingColumns} onChange={(value) => setFieldValue("match_column", value)} onRefresh={loadColumns} /></Card>}
      {["upsert", "update"].includes(values.operation) && values.data_mode === "manual" && <Card><Label>Value of Column to Match On</Label><Field name="match_value" className={inputClass} /></Card>}
      {MAPPED_OPERATIONS.includes(values.operation) && values.data_mode === "manual" && <ColumnValues columns={columns} operation={values.operation} />}

      {values.operation === "delete_table" && values.delete_command === "delete" && <Card><Label>Select Rows</Label><Field as="textarea" rows={5} name="where" className={inputClass} placeholder='[{"column":"status","condition":"=","value":"active"}]' /></Card>}
      {values.operation === "delete_table" && <Card><Label>Combine Conditions</Label><Field as="select" name="combine_conditions" className={inputClass}><option value="AND">AND</option><option value="OR">OR</option></Field></Card>}

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
