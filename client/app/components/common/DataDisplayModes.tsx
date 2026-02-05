import React, { useState } from 'react';
import { Code, Table, FileText, ChevronDown, Copy, Check } from '../../icons/index';

export type DisplayMode = 'schema' | 'table' | 'json';

interface DataDisplayModesProps {
  data: any;
  className?: string;
  defaultMode?: DisplayMode;
}

interface DisplayModeOption {
  id: DisplayMode;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
}

const displayModes: DisplayModeOption[] = [
  {
    id: 'schema',
    label: 'Schema',
    icon: FileText,
    description: 'Structured overview with data types',
  },
  {
    id: 'table', 
    label: 'Table',
    icon: Table,
    description: 'Tabular view for arrays and objects',
  },
  {
    id: 'json',
    label: 'JSON',
    icon: Code,
    description: 'Raw JSON with syntax highlighting',
  },
];

export default function DataDisplayModes({
  data,
  className = '',
  defaultMode = 'schema',
}: DataDisplayModesProps) {
  const [selectedMode, setSelectedMode] = useState<DisplayMode>(defaultMode);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      const textToCopy = typeof data === 'object' 
        ? JSON.stringify(data, null, 2)
        : String(data);
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };

  const renderSchemaView = (obj: any, depth: number = 0): React.ReactNode => {
    if (obj === null || obj === undefined) {
      return <span className="text-gray-500 italic">null</span>;
    }

    if (Array.isArray(obj)) {
      return (
        <div className={`${depth > 0 ? 'ml-4' : ''}`}>
          <div className="text-blue-400 text-sm font-medium mb-2">
            Array ({obj.length} items)
          </div>
          {obj.length > 0 && (
            <div className="border-l-2 border-gray-600 pl-3">
              <div className="text-gray-400 text-xs mb-2">Item structure:</div>
              {renderSchemaView(obj[0], depth + 1)}
            </div>
          )}
        </div>
      );
    }

    if (typeof obj === 'object') {
      const entries = Object.entries(obj);
      return (
        <div className={`${depth > 0 ? 'ml-4' : ''} space-y-2`}>
          {entries.map(([key, value]) => (
            <div key={key} className="flex items-start gap-3">
              <div className="text-green-400 font-medium text-sm min-w-0 flex-shrink-0">
                {key}
              </div>
              <div className="text-gray-400 text-xs self-center">:</div>
              <div className="min-w-0 flex-1">
                {typeof value === 'object' ? (
                  renderSchemaView(value, depth + 1)
                ) : (
                  <div className="flex items-center gap-2">
                    {typeof value === 'string' && value.length > 50 ? (
                      <span className="text-gray-300 text-sm">
                        {value.substring(0, 50)}...
                      </span>
                    ) : (
                      <span className="text-gray-300 text-sm">
                        {String(value)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      );
    }

    return (
      <div className="flex items-center gap-2">
        <span className="text-gray-300">{String(obj)}</span>
      </div>
    );
  };

  const renderTableView = (obj: any): React.ReactNode => {
    // Handle array data
    if (Array.isArray(obj)) {
      if (obj.length === 0) {
        return (
          <div className="text-gray-400 text-center py-8">
            <Table className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No data to display</p>
          </div>
        );
      }

      // Get all unique keys from all objects in array
      const allKeys = new Set<string>();
      obj.forEach(item => {
        if (typeof item === 'object' && item !== null) {
          Object.keys(item).forEach(key => allKeys.add(key));
        }
      });

      const keys = Array.from(allKeys);

      if (keys.length === 0) {
        return (
          <div className="text-gray-400 text-center py-8">
            <Table className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>Array contains primitive values, not objects</p>
          </div>
        );
      }

      return (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-600">
                {keys.map(key => (
                  <th key={key} className="text-left p-3 text-green-400 font-medium">
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {obj.map((item, index) => (
                <tr key={index} className="border-b border-gray-700/50 hover:bg-gray-800/30">
                  {keys.map(key => (
                    <td key={key} className="p-3 text-gray-300 max-w-xs">
                      {item && typeof item === 'object' ? (
                        typeof item[key] === 'object' ? (
                          <span className="text-gray-500 italic">
                            {Array.isArray(item[key]) 
                              ? `[${item[key].length} items]`
                              : '{object}'}
                          </span>
                        ) : (
                          <span className="break-words">
                            {String(item[key] || '—')}
                          </span>
                        )
                      ) : (
                        <span className="text-gray-500 italic">—</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    // Handle object data as key-value table
    if (typeof obj === 'object' && obj !== null) {
      const entries = Object.entries(obj);
      
      if (entries.length === 0) {
        return (
          <div className="text-gray-400 text-center py-8">
            <Table className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No data to display</p>
          </div>
        );
      }

      return (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-600">
                <th className="text-left p-3 text-green-400 font-medium w-1/3">
                  Property
                </th>
                <th className="text-left p-3 text-green-400 font-medium w-1/6">
                  Type
                </th>
                <th className="text-left p-3 text-green-400 font-medium">
                  Value
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map(([key, value]) => (
                <tr key={key} className="border-b border-gray-700/50 hover:bg-gray-800/30">
                  <td className="p-3 text-blue-300 font-medium">
                    {key}
                  </td>
                  <td className="p-3 text-purple-400 text-xs">
                    {Array.isArray(value) ? `array[${value.length}]` : typeof value}
                  </td>
                  <td className="p-3 text-gray-300 max-w-xs">
                    {typeof value === 'object' && value !== null ? (
                      <span className="text-gray-500 italic">
                        {Array.isArray(value) 
                          ? `[${value.length} items]`
                          : `{${Object.keys(value).length} properties}`}
                      </span>
                    ) : (
                      <span className="break-words">
                        {String(value)}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    // Fallback for primitive values
    return (
      <div className="text-gray-400 text-center py-8">
        <Table className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>Table view is not available for primitive values</p>
      </div>
    );
  };

  const renderJsonView = (obj: any): React.ReactNode => {
    const jsonString = JSON.stringify(obj, null, 2);
    return (
      <pre className="text-sm text-gray-300 whitespace-pre-wrap break-words">
        {jsonString}
      </pre>
    );
  };

  const renderContent = (): React.ReactNode => {
    switch (selectedMode) {
      case 'schema':
        return renderSchemaView(data);
      case 'table':
        return renderTableView(data);
      case 'json':
        return renderJsonView(data);
      default:
        return renderJsonView(data);
    }
  };

  return (
    <div className={`w-full ${className}`}>
      {/* Mode Selector */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-700/50">
        <div className="flex items-center gap-2">
          {displayModes.map((mode) => {
            const Icon = mode.icon;
            return (
              <button
                key={mode.id}
                onClick={() => setSelectedMode(mode.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedMode === mode.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700/50 text-gray-300 hover:bg-gray-600/50 hover:text-white'
                }`}
                title={mode.description}
              >
                <Icon className="w-4 h-4" />
                {mode.label}
              </button>
            );
          })}
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-gray-700/50 text-gray-300 hover:bg-gray-600/50 hover:text-white transition-colors"
          title="Copy data to clipboard"
        >
          {copied ? (
            <>
              <Check className="w-4 h-4 text-green-400" />
              <span className="text-green-400">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-4 h-4" />
              Copy
            </>
          )}
        </button>
      </div>

      {/* Content Display */}
      <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-700/30 max-h-96 overflow-auto">
        {renderContent()}
      </div>
    </div>
  );
}