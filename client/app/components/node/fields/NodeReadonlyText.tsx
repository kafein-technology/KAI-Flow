import { useCallback, useEffect, useMemo } from "react";
import { config } from "../../../lib/config";
import type { NodeProperty } from "../types";

interface NodeReadonlyTextProps {
  property: NodeProperty;
  values: any;
  setFieldValue?: (name: string, value: any) => void;
}

export const NodeReadonlyText = ({ property, values, setFieldValue }: NodeReadonlyTextProps) => {
  // Webhook exact URL için dinamik hesaplama
  const computedValue = useMemo(() => {
    // Eğer webhook_exact_url field'ı ise ve path değeri varsa, dinamik olarak hesapla
    if (property.name === "webhook_exact_url") {
      const pathValue = (values?.path || "").trim();
      if (pathValue) {
        const baseUrl = config.API_BASE_URL || window.location.origin;
        const basePath = window.VITE_BASE_PATH || '';
        const environment = values?.webhook_environment || "test";
        const prefix = environment === "production"
          ? `${config.API_VERSION}/webhook`
          : `${config.API_VERSION}/webhook-test`;
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
    return (
      (values && (values as any)[property.name]) ??
      (property.default as string) ??
      ""
    );
  }, [computedValue, values, property.name, property.default]);

  // path değiştiğinde webhook_exact_url'i güncelle
  useEffect(() => {
    if (property.name === "webhook_exact_url" && setFieldValue && computedValue) {
      setFieldValue("webhook_exact_url", computedValue);
    }
  }, [property.name, computedValue, setFieldValue]);

  const handleCopy = useCallback(() => {
    if (!value) return;
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(value).catch(() => {
        // Yut – sessiz failure
      });
    }
  }, [value]);

  return (
    <div
      className={`${property?.colSpan ? `col-span-${property?.colSpan}` : "col-span-2"
        }`}
      key={property.name}
    >
      <label className="text-white text-sm font-medium mb-2 block">
        {property.displayName}
      </label>
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
          className="px-3 py-2 text-xs rounded bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-600"
        >
          Copy
        </button>
      </div>
      {property.hint && (
        <p className="text-slate-400 text-xs bg-slate-900/30 mt-1">
          {property.hint}
        </p>
      )}
    </div>
  );
};


