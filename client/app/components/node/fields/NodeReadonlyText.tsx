import { useCallback, useEffect, useMemo } from "react";
import { config } from "../../../lib/config";
import { useClipboardFeedback } from "../../../hooks/useClipboardFeedback";
import type { NodeProperty } from "../types";
import { getActiveSessionId } from "../../../services/chatService";
import { useWorkflows } from "../../../stores/workflows";
import { FieldLabel, getFieldHelpText } from "./FieldLabel";

interface NodeReadonlyTextProps {
  property: NodeProperty;
  values: Record<string, unknown>;
  setFieldValue?: (name: string, value: unknown) => unknown;
}

export const NodeReadonlyText = ({ property, values, setFieldValue }: NodeReadonlyTextProps) => {
  const { currentWorkflow } = useWorkflows();
  const { copy } = useClipboardFeedback();
  const displayOptions = property?.displayOptions || {};
  const show = displayOptions.show || {};
  const isVisible = Object.entries(show).every(
    ([dependencyName, validValue]) => values[dependencyName] === validValue,
  );

  // Webhook exact URL için dinamik hesaplama
  const computedValue = useMemo(() => {
    // Eğer webhook_exact_url field'ı ise ve path değeri varsa, dinamik olarak hesapla
    if (property.name === "webhook_exact_url") {
      const pathValue = String(values?.path || "").trim();
      if (pathValue) {
        const baseUrl = config.API_BASE_URL || window.location.origin;
        const environment = String(values?.webhook_environment || "test");
        const prefix = environment === "production"
          ? `/${config.API_START}/${config.API_VERSION_ONLY}/webhook`
          : `/${config.API_START}/${config.API_VERSION_ONLY}/webhook-test`;
        return `${baseUrl}${prefix}/${pathValue}`;
      }
    }
    return null;
  }, [property.name, values?.path, values?.webhook_environment]);

  // Değer hesaplama: computed value varsa onu kullan, yoksa values veya default
  const value: string = useMemo(() => {
    if (computedValue) {
      return computedValue;
    }
    return String(values[property.name] ?? property.default ?? "");
  }, [computedValue, values, property.name, property.default]);

  // path değiştiğinde webhook_exact_url'i güncelle
  useEffect(() => {
    if (isVisible && property.name === "webhook_exact_url" && setFieldValue && computedValue) {
      setFieldValue("webhook_exact_url", computedValue);
    }
  }, [property.name, computedValue, isVisible, setFieldValue]);

  // session_id için aktif session ID'yi çek
  useEffect(() => {
    if (isVisible && property.name === "session_id" && values.session_mode === "automatic" && setFieldValue) {
      getActiveSessionId(currentWorkflow?.id).then(response => {
        if (response?.session_id) {
          setFieldValue("session_id", response.session_id);
        }
      }).catch(err => {
        console.error("Failed to fetch active session ID:", err);
      });
    }
  }, [property.name, setFieldValue, values.session_mode, currentWorkflow?.id, isVisible]);

  const handleCopy = useCallback(() => {
    void copy(value);
  }, [copy, value]);

  if (!isVisible) return null;

  return (
    <div
      className={`${property?.colSpan ? `col-span-${property?.colSpan}` : "col-span-2"
        }`}
      key={property.name}
    >
      <FieldLabel
        label={property.displayName}
        helpText={getFieldHelpText(property)}
      />
      <div className="flex items-center gap-2">
        <input
          type="text"
          readOnly
          value={value}
          className="input input-bordered w-full bg-slate-900/80 text-white text-sm rounded px-4 py-3 border border-gray-600 focus:ring-1 focus:ring-blue-500/20 cursor-default"
          placeholder={property.placeholder}
        />
        <button
          type="button"
          onClick={handleCopy}
          disabled={!value}
          aria-label={`Copy ${property.displayName || "value"} to clipboard`}
          className="px-3 py-2 text-xs rounded bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Copy
        </button>
      </div>
    </div>
  );
};


