import React from "react";
import { Power, PowerOff } from "lucide-react";

interface ToggleSwitchProps {
  isActive: boolean;
  onToggle: (isActive: boolean) => void;
  disabled?: boolean;
  size?: "sm" | "md" | "lg";
  showIcon?: boolean;
  label?: string;
  description?: string;
  activeIcon?: React.ReactNode;
  inactiveIcon?: React.ReactNode;
}

export default function ToggleSwitch({
  isActive,
  onToggle,
  disabled = false,
  size = "md",
  showIcon = true,
  label,
  description,
  activeIcon,
  inactiveIcon,
}: ToggleSwitchProps) {
  const sizeClasses = {
    sm: "w-10 h-6",
    md: "w-12 h-7",
    lg: "w-14 h-8",
  };

  const iconSize = {
    sm: "w-3 h-3",
    md: "w-4 h-4",
    lg: "w-5 h-5",
  };

  const handleToggle = () => {
    if (!disabled) {
      onToggle(!isActive);
    }
  };

  return (
    <div className="flex items-center gap-3">
      {/* Toggle Switch */}
      <button
        type="button"
        onClick={handleToggle}
        disabled={disabled}
        className={`
          relative inline-flex items-center justify-center
          ${sizeClasses[size]}
          rounded-full transition-all duration-300 ease-in-out
          focus:outline-none focus:ring-2 focus:ring-offset-2
          ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}
          ${
            isActive
              ? "bg-gradient-to-r from-green-500 to-emerald-500 shadow-lg shadow-green-500/25"
              : "bg-gradient-to-r from-gray-400 to-gray-500 shadow-lg shadow-gray-400/25"
          }
          hover:shadow-xl
        `}
      >
        {/* Toggle Circle */}
        <span
          className={`
            absolute left-1 inline-block
            ${size === "sm" ? "w-4 h-4" : size === "md" ? "w-5 h-5" : "w-6 h-6"}
            bg-white rounded-full transition-all duration-300 ease-in-out
            shadow-lg transform
            ${isActive ? "translate-x-5" : "translate-x-0"}
          `}
        >
          {/* Icon inside circle */}
          {showIcon && (
            <div className="w-full h-full flex items-center justify-center">
              {isActive ? (
                activeIcon || <Power className={`${iconSize[size]} text-green-600`} />
              ) : (
                inactiveIcon || <PowerOff className={`${iconSize[size]} text-gray-500`} />
              )}
            </div>
          )}
        </span>

        {/* Background Pattern */}
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-white/20 to-transparent opacity-30" />
      </button>

      {/* Label and Description */}
      {(label || description) && (
        <div className="flex flex-col">
          {label && (
            <span
              className={`font-medium ${
                isActive ? "text-green-700" : "text-gray-600"
              }`}
            >
              {label}
            </span>
          )}
          {description && (
            <span className="text-xs text-gray-500">{description}</span>
          )}
        </div>
      )}
    </div>
  );
}

// Compact version for cards
export function CompactToggleSwitch({
  isActive,
  onToggle,
  disabled = false,
  activeIcon,
  inactiveIcon,
}: {
  isActive: boolean;
  onToggle: (isActive: boolean) => void;
  disabled?: boolean;
  activeIcon?: React.ReactNode;
  inactiveIcon?: React.ReactNode;
}) {
  return (
    <ToggleSwitch
      isActive={isActive}
      onToggle={onToggle}
      disabled={disabled}
      size="sm"
      showIcon={true}
      activeIcon={activeIcon}
      inactiveIcon={inactiveIcon}
    />
  );
}
