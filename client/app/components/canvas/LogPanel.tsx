import React, { useEffect, useRef, useCallback, useMemo } from 'react';
import { Terminal, X, Trash2, Search, ChevronDown, ChevronUp, ArrowUp, ArrowDown } from 'lucide-react';
import { useLogStream } from '../../lib/useLogStream';

interface LogPanelProps {
  isOpen: boolean;
  onClose: () => void;
  height: number;
  onHeightChange: (height: number) => void;
}

interface SearchMatch {
  lineIndex: number;
  startIndex: number;
  length: number;
}

export default function LogPanel({ isOpen, onClose, height, onHeightChange }: LogPanelProps) {
  const [searchTerm, setSearchTerm] = React.useState('');
  const [matchCase, setMatchCase] = React.useState(false);
  const [wholeWords, setWholeWords] = React.useState(false);
  const [useRegex, setUseRegex] = React.useState(false);
  const [currentMatchIndex, setCurrentMatchIndex] = React.useState(-1);
  const [levelFilter, setLevelFilter] = React.useState<string>('ALL');
  const [autoScroll, setAutoScroll] = React.useState(true);
  const [userScrolledUp, setUserScrolledUp] = React.useState(false);

  // Connection is established once at mount and kept alive to buffer logs in the background
  const { logs, isConnected, error, clearLogs } = useLogStream(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const isResizing = useRef(false);

  // Drag-to-resize implementation
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isResizing.current = true;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    e.preventDefault();
  }, [onHeightChange]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing.current) return;
    const newHeight = window.innerHeight - e.clientY;
    if (newHeight >= 120 && newHeight <= window.innerHeight * 0.85) {
      onHeightChange(newHeight);
    }
  }, [onHeightChange]);

  const handleMouseUp = useCallback(() => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }, [handleMouseMove]);

  // Clean up resize listeners
  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

  // Filter logs ONLY by level
  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      if (levelFilter === 'ALL') return true;
      return (
        (levelFilter === 'INFO' && log.toUpperCase().includes('INFO')) ||
        (levelFilter === 'WARNING' && (log.toUpperCase().includes('WARN') || log.toUpperCase().includes('WARNING'))) ||
        (levelFilter === 'ERROR' && (log.toUpperCase().includes('ERROR') || log.toUpperCase().includes('CRITICAL'))) ||
        (levelFilter === 'DEBUG' && (log.toUpperCase().includes('DEBUG') || log.toUpperCase().includes('TRACE')))
      );
    });
  }, [logs, levelFilter]);

  const escapeRegExp = (str: string) => {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  };

  // Find all matches in current level-filtered logs
  const matches = useMemo<SearchMatch[]>(() => {
    if (!searchTerm) return [];
    
    try {
      let pattern = searchTerm;
      if (!useRegex) {
        pattern = escapeRegExp(searchTerm);
      }
      if (wholeWords) {
        pattern = `\\b${pattern}\\b`;
      }
      
      const regex = new RegExp(pattern, matchCase ? 'g' : 'gi');
      const foundMatches: SearchMatch[] = [];
      
      filteredLogs.forEach((log, lineIndex) => {
        regex.lastIndex = 0;
        let match;
        const isZeroLength = regex.source === '' || regex.source === '(?:)';
        
        while ((match = regex.exec(log)) !== null) {
          foundMatches.push({
            lineIndex,
            startIndex: match.index,
            length: match[0].length,
          });
          if (isZeroLength || match[0].length === 0) {
            regex.lastIndex++;
          }
        }
      });
      
      return foundMatches;
    } catch (e) {
      return [];
    }
  }, [filteredLogs, searchTerm, matchCase, wholeWords, useRegex]);

  // Coordinate match selection
  useEffect(() => {
    if (matches.length > 0) {
      if (currentMatchIndex < 0 || currentMatchIndex >= matches.length) {
        setCurrentMatchIndex(matches.length - 1); // Focus last match by default
      }
    } else {
      setCurrentMatchIndex(-1);
    }
  }, [matches]);

  // Scroll current match to the center of the terminal screen
  useEffect(() => {
    if (currentMatchIndex >= 0 && currentMatchIndex < matches.length) {
      const match = matches[currentMatchIndex];
      const element = document.getElementById(`log-line-${match.lineIndex}`);
      if (element) {
        element.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    }
  }, [currentMatchIndex, matches]);

  // Autoscroll logic
  const scrollToBottom = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    if (autoScroll && !userScrolledUp) {
      scrollToBottom();
    }
  }, [filteredLogs, autoScroll, userScrolledUp, scrollToBottom]);

  // Detect user scroll up
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 30;
    if (isAtBottom) {
      setUserScrolledUp(false);
    } else {
      setUserScrolledUp(true);
    }
  };

  const handleResumeAutoScroll = () => {
    setUserScrolledUp(false);
    scrollToBottom();
  };

  // Render log lines with layout-stable highlights (no padding, border, or bold shifts)
  const renderLogLine = (logText: string, lineIndex: number) => {
    const lineMatches = matches.filter((m) => m.lineIndex === lineIndex);
    if (lineMatches.length === 0) {
      return logText;
    }

    const sortedMatches = [...lineMatches].sort((a, b) => a.startIndex - b.startIndex);
    const elements: React.ReactNode[] = [];
    let lastIndex = 0;

    sortedMatches.forEach((match, idx) => {
      const globalIdx = matches.findIndex(
        (m) => m.lineIndex === lineIndex && m.startIndex === match.startIndex
      );
      const isFocused = globalIdx === currentMatchIndex;

      // Prefix text
      if (match.startIndex > lastIndex) {
        elements.push(
          <span key={`text-${idx}`}>
            {logText.substring(lastIndex, match.startIndex)}
          </span>
        );
      }

      // Highlighted match text (no padding, border, margins, or bold weight to avoid layout shifts)
      const matchText = logText.substring(match.startIndex, match.startIndex + match.length);
      elements.push(
        <mark
          key={`match-${idx}`}
          className={`rounded-none font-mono ${
            isFocused
              ? 'bg-blue-600 text-white'
              : 'bg-blue-600/30 text-slate-100'
          }`}
        >
          {matchText}
        </mark>
      );

      lastIndex = match.startIndex + match.length;
    });

    if (lastIndex < logText.length) {
      elements.push(
        <span key="text-end">
          {logText.substring(lastIndex)}
        </span>
      );
    }

    return <>{elements}</>;
  };

  return (
    <div
      style={{ height: `${height}px`, display: isOpen ? 'flex' : 'none' }}
      className="fixed bottom-0 left-16 right-0 z-40 bg-[#0C0C0E]/95 border-t border-gray-800/80 backdrop-blur-md shadow-2xl flex flex-col font-mono select-none"
    >
      {/* Resizer Handle */}
      <div
        onMouseDown={handleMouseDown}
        className="absolute top-0 left-0 right-0 h-1.5 cursor-ns-resize hover:bg-blue-600/50 active:bg-blue-600/70 transition-colors z-50"
        title="Drag to resize panel"
      />

      {/* Control Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800/60 bg-[#121215]/90 text-sm font-mono">
        {/* Left Side: Status Info */}
        <div className="flex items-center gap-3 font-mono">
          <div className="flex items-center gap-1.5 text-slate-100 font-semibold font-mono">
            <Terminal className="w-4 h-4 text-blue-400" />
            <span className="font-mono">Backend Logs</span>
          </div>

          {/* Connection Status Indicator */}
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-gray-900 border border-gray-800 text-[11px] font-medium text-slate-300 font-mono">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-gray-600'}`} />
            <span className="font-mono">{isConnected ? 'Connected' : 'Offline'}</span>
          </div>

          {error && (
            <span className="text-xs text-rose-400 flex items-center gap-1 font-mono">
              • Connection error
            </span>
          )}
        </div>

        {/* Middle: Modern IDE Search Bar & Options */}
        <div className="flex items-center gap-4 flex-1 max-w-xl mx-8 font-mono">
          <div className="flex items-center gap-2 bg-[#080809] border border-gray-800 rounded-lg px-2.5 py-1.5 max-w-md w-full relative font-mono">
            <Search className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mr-1" />
            <input
              type="text"
              placeholder="Search..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentMatchIndex(-1);
              }}
              className="bg-transparent text-xs text-slate-100 placeholder-slate-500 focus:outline-none flex-1 font-mono pr-20"
            />
            {/* Search Option Toggles */}
            <div className="flex items-center gap-1 absolute right-2 top-1/2 -translate-y-1/2">
              <button
                onClick={() => setMatchCase(!matchCase)}
                className={`px-1 py-0.5 text-[9px] rounded font-bold font-mono border transition-all ${
                  matchCase
                    ? 'bg-blue-600/30 text-blue-400 border-blue-500/40'
                    : 'text-slate-500 border-transparent hover:text-slate-300'
                }`}
                title="Match Case (Aa)"
              >
                Aa
              </button>
              <button
                onClick={() => setWholeWords(!wholeWords)}
                className={`px-1 py-0.5 text-[9px] rounded font-bold font-mono border transition-all ${
                  wholeWords
                    ? 'bg-blue-600/30 text-blue-400 border-blue-500/40'
                    : 'text-slate-500 border-transparent hover:text-slate-300'
                }`}
                title="Match Whole Word (\\b)"
              >
                \b
              </button>
              <button
                onClick={() => setUseRegex(!useRegex)}
                className={`px-1 py-0.5 text-[9px] rounded font-bold font-mono border transition-all ${
                  useRegex
                    ? 'bg-blue-600/30 text-blue-400 border-blue-500/40'
                    : 'text-slate-500 border-transparent hover:text-slate-300'
                }`}
                title="Use Regular Expression (.*)"
              >
                .*
              </button>
            </div>
          </div>

          {/* Navigation and Match Count */}
          {searchTerm && (
            <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono flex-shrink-0">
              <span className="font-mono bg-gray-900 border border-gray-800 px-2 py-0.5 rounded text-[11px]">
                {matches.length > 0 ? `${currentMatchIndex + 1} of ${matches.length}` : '0 of 0'}
              </span>
              <button
                onClick={() => {
                  if (matches.length > 0) {
                    setCurrentMatchIndex((prev) => (prev - 1 + matches.length) % matches.length);
                    setAutoScroll(false);
                  }
                }}
                disabled={matches.length === 0}
                className="p-1 hover:text-white rounded hover:bg-gray-800 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                title="Previous Match"
              >
                <ChevronUp className="w-4 h-4" />
              </button>
              <button
                onClick={() => {
                  if (matches.length > 0) {
                    setCurrentMatchIndex((prev) => (prev + 1) % matches.length);
                    setAutoScroll(false);
                  }
                }}
                disabled={matches.length === 0}
                className="p-1 hover:text-white rounded hover:bg-gray-800 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                title="Next Match"
              >
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Right Side: Actions & Level Filter */}
        <div className="flex items-center gap-1.5 font-mono">
          {/* Level Filter Pills */}
          <div className="flex items-center gap-1 bg-[#080809] border border-gray-800 rounded-lg p-0.5 font-mono mr-2">
            {['ALL', 'INFO', 'WARNING', 'ERROR', 'DEBUG'].map((level) => (
              <button
                key={level}
                onClick={() => setLevelFilter(level)}
                className={`px-2 py-0.5 text-[10px] rounded-md font-medium transition-all font-mono ${
                  levelFilter === level
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 border border-transparent'
                }`}
              >
                {level}
              </button>
            ))}
          </div>

          {/* Scroll to Top */}
          <button
            onClick={() => {
              if (containerRef.current) {
                containerRef.current.scrollTop = 0;
                setUserScrolledUp(true);
              }
            }}
            className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-gray-800 transition-colors font-mono"
            title="Scroll to Top"
          >
            <ArrowUp className="w-4 h-4" />
          </button>

          {/* Scroll to Bottom */}
          <button
            onClick={() => {
              if (containerRef.current) {
                containerRef.current.scrollTop = containerRef.current.scrollHeight;
                setUserScrolledUp(false);
              }
            }}
            className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-gray-800 transition-colors font-mono"
            title="Scroll to Bottom"
          >
            <ArrowDown className="w-4 h-4" />
          </button>

          {/* Clear Logs */}
          <button
            onClick={clearLogs}
            className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-gray-800 transition-colors font-mono"
            title="Clear Console"
          >
            <Trash2 className="w-4 h-4" />
          </button>

          {/* Auto-scroll toggle */}
          <button
            onClick={() => {
              const nextVal = !autoScroll;
              setAutoScroll(nextVal);
              if (nextVal) {
                setUserScrolledUp(false);
                scrollToBottom();
              }
            }}
            className={`px-2 py-1 text-xs rounded-lg font-medium transition-colors border font-mono ${
              autoScroll
                ? 'bg-blue-600/10 text-blue-400 border-blue-500/20'
                : 'text-slate-400 border-gray-800 hover:bg-gray-800'
            }`}
            title="Auto-scroll to bottom on new logs"
          >
            Auto-Scroll
          </button>

          {/* Divider */}
          <div className="w-[1px] h-4 bg-gray-800 mx-1"></div>

          {/* Close Panel */}
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-gray-800 transition-colors font-mono"
            title="Hide logs panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Terminal Output Area */}
      <div className="relative flex-1 min-h-0 bg-[#09090B]">
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="w-full h-full overflow-y-auto px-4 py-3 font-mono text-sm leading-relaxed text-slate-100 selection:bg-blue-600/30 whitespace-pre-wrap select-text scrollbar-thin"
        >
          {filteredLogs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 italic select-none font-mono">
              <span className="font-mono">No logs found</span>
            </div>
          ) : (
            filteredLogs.map((logText, idx) => (
              <div
                key={idx}
                id={`log-line-${idx}`}
                className="py-0.5 border-b border-gray-900/20 hover:bg-gray-900/30 transition-colors font-mono text-slate-100 whitespace-pre-wrap select-text text-sm leading-relaxed"
              >
                {renderLogLine(logText, idx)}
              </div>
            ))
          )}
        </div>

        {/* Scroll pause overlay indicator */}
        {userScrolledUp && autoScroll && filteredLogs.length > 0 && (
          <button
            onClick={handleResumeAutoScroll}
            className="absolute bottom-4 right-6 flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600/90 text-white rounded-lg shadow-lg hover:bg-blue-500 active:scale-95 transition-all z-10 backdrop-blur-sm border border-blue-400/20 font-mono"
          >
            <ChevronDown className="w-3.5 h-3.5" />
            <span className="font-mono">Resume Auto-scroll</span>
          </button>
        )}
      </div>
    </div>
  );
}
