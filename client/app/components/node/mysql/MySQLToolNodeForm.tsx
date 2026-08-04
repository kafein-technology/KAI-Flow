import { Field, Form, Formik, useFormikContext } from "formik";
import { Check, ChevronDown, Loader2, RefreshCw, Settings, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import TabNavigation from "../../common/TabNavigation";
import { NodeCredentialSelect } from "../fields";
import { FieldLabel } from "../fields/FieldLabel";
import type { GenericData, NodeProperty } from "../types";
import { getMySQLTables, type MySQLTableInfo } from "~/services/mysqlService";

interface MySQLToolNodeFormProps {
  configData?: any;
  onSave?: (values: any) => void;
  onCancel: () => void;
  onChange?: (values: GenericData) => void;
}

const inputClass =
  "w-full rounded-md border border-slate-600 bg-[#10182c] px-3 py-2.5 text-sm text-white outline-none transition focus:border-blue-500";

const parseAllowedTables = (value: unknown) =>
  String(value || "").split(",").map((table) => table.trim()).filter(Boolean);

function Label({ children, help, bold = true }: { children: React.ReactNode; help?: string; bold?: boolean }) {
  return (
    <FieldLabel
      label={children}
      helpText={help}
      className={`mb-2 text-sm text-slate-100 ${bold ? "font-medium" : "font-normal"}`}
    />
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

function ToggleCard({ label, help, bold, checked, onChange }: { label: string; help?: string; bold?: boolean; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <Label help={help} bold={bold}>{label}</Label>
        <Toggle checked={checked} onChange={onChange} />
      </div>
    </Card>
  );
}

function MultiSearchableSelect({
  values,
  options,
  loading,
  placeholder,
  onChange,
  onRefresh,
}: {
  values: string[];
  options: string[];
  loading?: boolean;
  placeholder?: string;
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
        <div className={`${inputClass} flex h-[42px] flex-nowrap items-center gap-1.5 overflow-x-auto py-1.5`} onClick={() => setOpen(true)}>
          {values.map((value) => (
            <span key={value} className="flex shrink-0 items-center gap-1 rounded bg-blue-500/20 px-2 py-1 text-xs text-blue-300">
              {value}
              <button type="button" onClick={(event) => { event.stopPropagation(); toggle(value); }}><X className="h-3 w-3" /></button>
            </span>
          ))}
          <input
            value={search}
            onFocus={() => setOpen(true)}
            onChange={(event) => { setSearch(event.target.value); setOpen(true); }}
            placeholder={values.length ? "" : placeholder}
            className="min-w-[80px] flex-1 shrink-0 bg-transparent py-1 text-sm outline-none"
          />
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
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

function MySQLToolFields({ activeTab, onChange }: { activeTab: string; onChange?: (values: GenericData) => void }) {
  const { values, setFieldValue, initialValues } = useFormikContext<Record<string, any>>();
  const [tables, setTables] = useState<MySQLTableInfo[]>([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const changeRef = useRef(onChange);
  const firstChange = useRef(true);
  changeRef.current = onChange;

  const loadTables = useCallback(async () => {
    if (!values.credential_id) { setTables([]); return; }
    setLoadingTables(true);
    try { setTables(await getMySQLTables(values.credential_id)); } catch { setTables([]); }
    finally { setLoadingTables(false); }
  }, [values.credential_id]);

  useEffect(() => { void loadTables(); }, [loadTables]);
  useEffect(() => {
    if (firstChange.current) { firstChange.current = false; return; }
    if (JSON.stringify(values) !== JSON.stringify(initialValues)) changeRef.current?.(values);
  }, [values, initialValues]);

  if (activeTab === "advanced") {
    return (
      <div className="grid grid-cols-1 gap-3 p-6">
        <Card>
          <Label help="Name the Agent uses when it calls this tool. Keep it stable so saved prompts keep working.">Tool Name</Label>
          <Field name="tool_name" className={inputClass} placeholder="mysql_database" />
        </Card>
        <Card>
          <Label help="Time reserved for opening the MySQL connection.">Connection Timeout (ms)</Label>
          <Field type="number" name="connection_timeout_ms" min={1000} max={300000} className={inputClass} />
        </Card>
      </div>
    );
  }

  const tableNames = tables.map((table) => table.name);
  const allowedTables: string[] = parseAllowedTables(values.allowed_tables);

  return (
    <div className="grid grid-cols-1 gap-3 p-6">
      <Card>
        <NodeCredentialSelect
          property={{ name: "credential_id", displayName: "Credential", type: "credential-select", serviceType: "mysql", required: true, placeholder: "Select Credential" } as NodeProperty}
          values={values}
          setFieldValue={setFieldValue}
        />
      </Card>
      <Card>
        <Label help="Tables the Agent may touch. Leave it empty to allow every table in the database.">Allowed Tables</Label>
        <MultiSearchableSelect
          values={allowedTables}
          options={tableNames}
          loading={loadingTables}
          placeholder="All tables in the database"
          onChange={(next) => setFieldValue("allowed_tables", next.join(","))}
          onRefresh={loadTables}
        />
        <p className="mt-1 text-xs text-slate-500">{allowedTables.length ? `${allowedTables.length} of ${tableNames.length} selected` : `All ${tableNames.length} tables`}</p>
      </Card>

      <ToggleCard
        label="Return All Rows"
        help="Let the Agent read every matching row instead of stopping at the row limit."
        checked={Boolean(values.return_all_rows)}
        onChange={(checked) => setFieldValue("return_all_rows", checked)}
      />
      {!values.return_all_rows && (
        <Card>
          <Label help="Maximum number of rows a single tool call may return while Return All Rows is off.">Maximum Rows</Label>
          <Field type="number" min="1" max="5000" name="max_rows" className={inputClass} />
        </Card>
      )}

      <p className="px-1 text-sm font-medium text-slate-100">Permissions</p>
      <ToggleCard
        label="Allow Read"
        help="Permit SELECT queries and schema lookups."
        bold={false}
        checked={Boolean(values.allow_read)}
        onChange={(checked) => setFieldValue("allow_read", checked)}
      />
      <ToggleCard
        label="Allow Insert"
        help="Permit INSERT statements that add new rows."
        bold={false}
        checked={Boolean(values.allow_insert)}
        onChange={(checked) => setFieldValue("allow_insert", checked)}
      />
      <ToggleCard
        label="Allow Update"
        help="Permit UPDATE statements that change existing rows."
        bold={false}
        checked={Boolean(values.allow_update)}
        onChange={(checked) => setFieldValue("allow_update", checked)}
      />
      <ToggleCard
        label="Allow Delete"
        help="Permit DELETE statements that remove rows."
        bold={false}
        checked={Boolean(values.allow_delete)}
        onChange={(checked) => setFieldValue("allow_delete", checked)}
      />
    </div>
  );
}

export default function MySQLToolNodeForm({ configData, onSave, onCancel, onChange }: MySQLToolNodeFormProps) {
  const properties = configData?.metadata?.properties || [];
  const initialValues = useMemo(() => ({
    ...properties.reduce((acc: Record<string, any>, property: NodeProperty) => {
      acc[property.name] = property.default ?? (property.type === "checkbox" ? false : "");
      return acc;
    }, {}),
    ...configData,
  }), [configData, properties]);
  const [activeTab, setActiveTab] = useState("basic");
  const tabs = [
    { id: "basic", label: "Basic", icon: Settings },
    { id: "advanced", label: "Advanced", icon: Settings },
  ];

  return (
    <div className="h-full w-full">
      <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} className="mb-4" />
      <Formik initialValues={initialValues} enableReinitialize onSubmit={(values) => onSave?.(values)}>
        <Form>
          <MySQLToolFields activeTab={activeTab} onChange={onChange} />
          <div className="hidden"><button type="submit">Save</button><button type="button" onClick={onCancel}>Cancel</button></div>
        </Form>
      </Formik>
    </div>
  );
}
