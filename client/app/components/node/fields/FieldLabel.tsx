import type { ReactNode } from "react";
import { useId } from "react";
import { CircleHelp } from "lucide-react";

interface FieldLabelProps {
  label: ReactNode;
  helpText?: string;
  className?: string;
  children?: ReactNode;
}

export const getFieldHelpText = (property: Record<string, any>) => {
  const helpText = property.hint ?? property.description;
  return typeof helpText === "string" && helpText.trim() ? helpText : undefined;
};

export const FieldLabel = ({
  label,
  helpText,
  className = "text-white text-sm font-medium mb-2",
  children,
}: FieldLabelProps) => {
  const tooltipId = useId();

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span>{label}</span>
      {helpText && (
        <span className="relative inline-flex items-center group">
          <button
            type="button"
            aria-label="Show field help"
            aria-describedby={tooltipId}
            className="inline-flex h-4 w-4 items-center justify-center text-slate-400 transition-colors hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            onMouseDown={(e) => e.stopPropagation()}
            onTouchStart={(e) => e.stopPropagation()}
          >
            <CircleHelp className="h-4 w-4" aria-hidden="true" />
          </button>
          <span
            id={tooltipId}
            role="tooltip"
            className="pointer-events-none invisible absolute left-0 top-full z-50 mt-2 w-64 whitespace-normal break-words rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-left text-xs font-normal leading-relaxed text-slate-200 opacity-0 shadow-xl shadow-black/40 transition-opacity duration-150 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
          >
            {helpText}
          </span>
        </span>
      )}
      {children}
    </div>
  );
};
