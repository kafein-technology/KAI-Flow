import { useCallback, useEffect } from "react";
import { Field } from "formik";
import type { NodeProperty } from "../types";
import { getActiveSessionId } from "../../../services/chatService";
import { useWorkflows } from "../../../stores/workflows";

interface NodeSessionIdProps {
    property: NodeProperty;
    values: any;
    setFieldValue?: (name: string, value: any) => void;
}

export const NodeSessionId = ({ property, values, setFieldValue }: NodeSessionIdProps) => {
    const { currentWorkflow } = useWorkflows();
    const isAutomatic = values.session_mode === "automatic" || values.session_mode === "auto";

    // Check if we need to fetch the active session ID (only in automatic mode)
    useEffect(() => {
        if (isAutomatic && setFieldValue) {
            getActiveSessionId(currentWorkflow?.id).then(response => {
                if (response?.session_id) {
                    setFieldValue(property.name, response.session_id);
                }
            }).catch(err => {
                console.error("Failed to fetch active session ID:", err);
            });
        }
    }, [isAutomatic, setFieldValue, property.name, currentWorkflow?.id]);

    const handleCopy = useCallback(() => {
        const value = values[property.name];
        if (!value) return;
        if (navigator?.clipboard?.writeText) {
            navigator.clipboard.writeText(value).catch(() => {
                // Silent failure
            });
        }
    }, [values, property.name]);

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
                <Field
                    name={property.name}
                    type="text"
                    readOnly={isAutomatic}
                    className={`input input-bordered w-full text-white text-sm rounded-lg px-4 py-3 border border-slate-600 focus:ring-1 focus:ring-blue-500/20 ${isAutomatic ? "bg-slate-900/80 cursor-default" : "bg-[#10182c] focus:border-blue-500 shadow-inner shadow-black/20"
                        }`}
                    placeholder={property.placeholder || (isAutomatic ? "Automatically generated..." : "Enter manual session ID...")}
                />
                {isAutomatic && (
                    <button
                        type="button"
                        onClick={handleCopy}
                        className="px-3 py-2 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-300 border border-slate-600 transition-colors shrink-0"
                    >
                        Copy
                    </button>
                )}
            </div>
            {property.description && (
                <p className="text-slate-400 text-[11px] leading-relaxed mt-1.5 px-1 opacity-80">
                    {property.description}
                </p>
            )}
            {property.hint && (
                <p className="text-slate-400 text-[11px] leading-relaxed mt-1 px-1 italic">
                    {property.hint}
                </p>
            )}
        </div>
    );
};
