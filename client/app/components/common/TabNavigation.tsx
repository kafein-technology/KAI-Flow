import React from "react";

// Type for icon component (since we're using local icons now)
type IconComponent = React.ComponentType<{ className?: string; size?: number }>;

interface Tab {
  id: string;
  label: string;
  icon: IconComponent;
  description?: string;
}

interface TabNavigationProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  className?: string;
}

export default function TabNavigation({
  tabs,
  activeTab,
  onTabChange,
  className = "",
}: TabNavigationProps) {
  return (
    <div
      className={`flex space-x-1 p-1 bg-slate-700/30 rounded-lg ${className}`}
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;

        return (
          <button
            key={tab.id}
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onTabChange(tab.id);
            }}
            className={`
            flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium
            transition-all duration-200 relative
            ${
              isActive
                ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                : "text-slate-400 hover:text-slate-300 hover:bg-slate-600/30"
            }
          `}
            title={tab.description}
          >
            <Icon className="w-3 h-3" />
            <span>{tab.label}</span>

            {/* Active indicator */}
            {isActive && (
              <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 w-1 h-0.5 bg-blue-400 rounded-full" />
            )}
          </button>
        );
      })}
    </div>
  );
}
