import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';

interface DataDisplayModesProps {
  data: any;
  className?: string;
  isInputPanel?: boolean;
  inputsMeta?: any;
  currentNodeName?: string;
  defaultMode?: string; // Kept for backward compatibility signatures
}

const DataTreeContext = React.createContext<{
  isInputPanel?: boolean;
  inputsMeta?: any;
  currentNodeName?: string;
} | null>(null);

function RenderPrimitiveValue({ val }: { val: any }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (val === null || val === undefined) {
    return <span className="text-gray-500 italic font-mono select-all">null</span>;
  }
  
  if (typeof val === 'string') {
    const threshold = 150;
    const isLong = val.length > threshold;
    
    if (isLong && !isExpanded) {
      const truncated = val.slice(0, threshold) + "...";
      return (
        <span 
          onClick={() => setIsExpanded(true)}
          className="text-emerald-400 font-mono break-all select-all cursor-pointer hover:underline hover:text-emerald-300"
          title="Click to expand"
        >
          "{truncated}"
        </span>
      );
    }
    
    return (
      <span 
        onClick={() => { if (isLong) setIsExpanded(false); }}
        className={`text-emerald-400 font-mono break-all select-all ${isLong ? 'cursor-pointer hover:underline hover:text-emerald-300' : ''}`}
        title={isLong ? "Click to collapse" : undefined}
      >
        "{val}"
      </span>
    );
  }
  
  if (typeof val === 'number') {
    return <span className="text-amber-400 font-mono select-all">{val}</span>;
  }
  
  if (typeof val === 'boolean') {
    return <span className="text-purple-400 font-semibold font-mono select-all">{val ? 'true' : 'false'}</span>;
  }
  
  const stringVal = String(val);
  const threshold = 150;
  const isLong = stringVal.length > threshold;
  
  if (isLong && !isExpanded) {
    const truncated = stringVal.slice(0, threshold) + "...";
    return (
      <span 
        onClick={() => setIsExpanded(true)}
        className="text-gray-300 font-mono select-all cursor-pointer hover:underline hover:text-gray-200"
        title="Click to expand"
      >
        {truncated}
      </span>
    );
  }
  
  return (
    <span 
      onClick={() => { if (isLong) setIsExpanded(false); }}
      className={`text-gray-300 font-mono select-all ${isLong ? 'cursor-pointer hover:underline hover:text-gray-200' : ''}`}
      title={isLong ? "Click to collapse" : undefined}
    >
      {stringVal}
    </span>
  );
}

function calculateJinjaExpression(path: string[], context: any) {
  if (!path || path.length === 0) return '';

  const normalizeForJinja = (name: string): string => {
    let normalized = name
      .toLowerCase()
      .replace(/[^a-z0-9_]/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_+|_+$/g, "");
    if (/^[0-9]/.test(normalized)) {
      normalized = "n_" + normalized;
    }
    return normalized || "node";
  };

  const buildPathString = (base: string, parts: string[]): string => {
    let resultPath = base;
    for (const part of parts) {
      const trimmedPart = String(part).trim();
      if (/^\d+$/.test(trimmedPart)) {
        resultPath += `[${trimmedPart}]`;
      } else {
        resultPath += `.${trimmedPart}`;
      }
    }
    return resultPath;
  };

  if (context?.isInputPanel) {
    const [rootKey, ...restPath] = path;
    const metaArray = context.inputsMeta?.[rootKey];
    if (metaArray && metaArray.length > 0) {
      const connection = metaArray[0];
      const sourceAlias = connection.sourceNodeAlias || connection.sourceNodeName;
      if (sourceAlias) {
        const normalizedAlias = normalizeForJinja(sourceAlias);
        const jinjaPath = buildPathString(normalizedAlias, restPath);
        return `\${{${jinjaPath}}}`;
      }
    }
    return `\${{${buildPathString(rootKey, restPath)}}}`;
  } else {
    const currentNodeAlias = context?.currentNodeName || 'node';
    const normalizedCurrentNode = normalizeForJinja(currentNodeAlias);
    const [rootKey, ...restPath] = path;
    if (rootKey === 'output') {
      return `\${{${buildPathString(normalizedCurrentNode, restPath)}}}`;
    } else {
      return `\${{${buildPathString(normalizedCurrentNode, path)}}}`;
    }
  }
}

interface JsonTreeItemProps {
  keyName?: string;
  value: any;
  isLast?: boolean;
  depth: number;
  path: string[];
}

function JsonTreeItem({ keyName, value, isLast = false, depth, path }: JsonTreeItemProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [copied, setCopied] = useState(false);
  const context = React.useContext(DataTreeContext);

  const isObject = value !== null && typeof value === 'object';
  const isArray = Array.isArray(value);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const text = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  const handleDragStart = (e: React.DragEvent) => {
    const jinjaExpr = calculateJinjaExpression(path, context);
    e.dataTransfer.setData("text/plain", jinjaExpr);
    e.dataTransfer.effectAllowed = "copy";
  };

  if (isObject) {
    const keys = isArray ? value : Object.keys(value);
    const size = isArray ? value.length : keys.length;

    if (size === 0) {
      return (
        <div className="flex items-center py-1 pl-4 font-mono text-sm">
          {keyName && <span className="text-sky-400 font-medium mr-1">{keyName}:</span>}
          <span className="text-gray-500">{isArray ? '[]' : '{}'}</span>
        </div>
      );
    }

    return (
      <div className="flex flex-col font-mono text-sm">
        {/* Header */}
        <div className="flex items-center group py-0.5 hover:bg-gray-800/20 rounded cursor-pointer" onClick={() => setIsOpen(!isOpen)}>
          <span className="p-0.5 mr-0.5 text-gray-500 hover:text-gray-300" onClick={(e) => e.stopPropagation()}>
            {isOpen ? (
              <ChevronDown className="w-3.5 h-3.5" onClick={() => setIsOpen(false)} />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" onClick={() => setIsOpen(true)} />
            )}
          </span>
          {keyName && (
            context?.isInputPanel ? (
              <span
                draggable
                onDragStart={handleDragStart}
                onClick={(e) => e.stopPropagation()}
                className="border border-gray-800 bg-gray-900/50 rounded px-1.5 py-0.5 text-xs text-sky-400 font-mono font-medium cursor-grab active:cursor-grabbing hover:bg-gray-800 transition-colors select-none flex items-center gap-1"
                title="Drag to drop Jinja variable"
              >
                <span className="text-[10px] text-gray-500 font-mono">☰</span>
                {keyName}
              </span>
            ) : (
              <span
                onClick={(e) => e.stopPropagation()}
                className="border border-gray-800 bg-gray-950/40 rounded px-1.5 py-0.5 text-xs text-sky-300 font-mono font-medium select-none flex items-center gap-1"
                title="Output key"
              >
                {keyName}
              </span>
            )
          )}
          {keyName && <span className="text-gray-500 mr-1.5">:</span>}
          <span className="text-gray-400 mr-2">{isArray ? '[' : '{'}</span>
          
          {!isOpen && (
            <>
              <span className="text-gray-500 text-xs italic mr-2">
                {isArray ? `${size} items` : `${size} keys`}
              </span>
              <span className="text-gray-400 mr-2">{isArray ? ']' : '}'}</span>
            </>
          )}

          {/* Copy node button */}
          <button
            onClick={handleCopy}
            className="opacity-0 group-hover:opacity-100 ml-2 p-1 text-gray-500 hover:text-gray-300 rounded transition-opacity"
            title={isArray ? "Copy array" : "Copy object"}
          >
            {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>

        {/* Children */}
        {isOpen && (
          <div className="border-l border-gray-800/80 ml-2 pl-4 flex flex-col">
            {isArray
              ? value.map((item: any, idx: number) => (
                  <JsonTreeItem
                    key={idx}
                    keyName={String(idx)}
                    value={item}
                    isLast={idx === value.length - 1}
                    depth={depth + 1}
                    path={[...path, String(idx)]}
                  />
                ))
              : Object.entries(value).map(([childKey, childValue], idx, arr) => (
                  <JsonTreeItem
                    key={childKey}
                    keyName={childKey}
                    value={childValue}
                    isLast={idx === arr.length - 1}
                    depth={depth + 1}
                    path={[...path, childKey]}
                  />
                ))}
          </div>
        )}

        {/* Footer */}
        {isOpen && (
          <div className="text-gray-400 py-0.5 pl-4">
            {isArray ? ']' : '}'}
          </div>
        )}
      </div>
    );
  }

  // Primitive value
  return (
    <div className="flex items-center group py-0.5 pl-4 hover:bg-gray-800/20 rounded font-mono text-sm">
      {keyName && (
        context?.isInputPanel ? (
          <span
            draggable
            onDragStart={handleDragStart}
            className="border border-gray-800 bg-gray-900/50 rounded px-1.5 py-0.5 text-xs text-sky-400 font-mono font-medium cursor-grab active:cursor-grabbing hover:bg-gray-800 transition-colors select-none flex items-center gap-1 mr-1 flex-shrink-0"
            title="Drag to drop Jinja variable"
          >
            <span className="text-[10px] text-gray-500 font-mono">☰</span>
            {keyName}
          </span>
        ) : (
          <span
            className="border border-gray-800 bg-gray-950/40 rounded px-1.5 py-0.5 text-xs text-sky-300 font-mono font-medium select-none flex items-center gap-1 mr-1 flex-shrink-0"
            title="Output key"
          >
            {keyName}
          </span>
        )
      )}
      {keyName && <span className="text-gray-500 mr-1.5 flex-shrink-0">:</span>}
      <div className="flex-1 min-w-0">
        <RenderPrimitiveValue val={value} />
      </div>
      
      {/* Copy primitive button */}
      <button
        onClick={handleCopy}
        className="opacity-0 group-hover:opacity-100 ml-2 p-1 text-gray-500 hover:text-gray-300 rounded transition-opacity flex-shrink-0"
        title="Copy value"
      >
        {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3 h-3" />}
      </button>
    </div>
  );
}

export default function DataDisplayModes({
  data,
  className = '',
  isInputPanel = false,
  inputsMeta,
  currentNodeName,
}: DataDisplayModesProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyAll = async () => {
    try {
      const textToCopy = typeof data === 'object' && data !== null
        ? JSON.stringify(data, null, 2)
        : String(data);
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };

  const isEmpty = data === null || data === undefined || (typeof data === 'object' && Object.keys(data).length === 0);

  return (
    <DataTreeContext.Provider value={{ isInputPanel, inputsMeta, currentNodeName }}>
      <div className={`w-full flex flex-col bg-gray-950/40 border border-gray-850 rounded-xl overflow-hidden ${className}`}>
        {/* Header bar */}
        <div className="flex items-center justify-between px-4 py-2 bg-gray-900/60 border-b border-gray-850">
          <span className="text-xs font-semibold text-gray-400 tracking-wider uppercase">
            Data Tree
          </span>

          <button
            onClick={handleCopyAll}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-gray-800/60 hover:bg-gray-700/60 text-gray-300 hover:text-white border border-gray-700/50 transition-all cursor-pointer"
            title="Copy full JSON"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-green-400" />
                <span className="text-green-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy Full JSON</span>
              </>
            )}
          </button>
        </div>

        {/* Main tree display area */}
        <div className="p-4 overflow-auto max-h-[500px] bg-gray-900/10">
          {isEmpty ? (
            <div className="text-gray-500 italic py-4 pl-4 text-sm font-mono">
              {"{ empty }"}
            </div>
          ) : (
            <JsonTreeItem value={data} depth={0} path={[]} />
          )}
        </div>
      </div>
    </DataTreeContext.Provider>
  );
}