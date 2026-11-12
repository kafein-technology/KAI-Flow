import React, { useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react';
import { Terminal, X, Trash2, Search, ChevronDown, ChevronUp, ArrowUp, ArrowDown, Download } from 'lucide-react';
import { useLogStream } from '../../lib/useLogStream';
import './LogPanel.css';

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
  const [searchNavigation, setSearchNavigation] = React.useState(0);

  // Connect only while the panel is open and frontend logging is enabled.
  const { logs, isConnected, error, clearLogs } = useLogStream(
    isOpen && window.VITE_ENABLE_LOGGING === 'true'
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const isResizing = useRef(false);
  const followTailRef = useRef(true);
  const navigateSearchRef = useRef(false);

  // Autoscroll logic
  const scrollToBottom = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, []);

  const pauseFollowing = useCallback(() => {
    followTailRef.current = false;
    setUserScrolledUp(true);
  }, []);

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

  // Keep selection in range, but navigate only after an explicit search action.
  // Streamed output must never recenter a match or resume tail following.
  useLayoutEffect(() => {
    const nextIndex = matches.length === 0 ? -1
      : currentMatchIndex < 0 ? matches.length - 1 : Math.min(currentMatchIndex, matches.length - 1);
    if (nextIndex !== currentMatchIndex) setCurrentMatchIndex(nextIndex);
    if (!navigateSearchRef.current || !isOpen) return;
    navigateSearchRef.current = false;
    const container = containerRef.current;
    const match = matches[nextIndex];
    const line = match && container?.querySelector<HTMLElement>(`[data-log-line="${match.lineIndex}"]`);
    if (container && line) {
      container.scrollTop += line.getBoundingClientRect().top - container.getBoundingClientRect().top
        - (container.clientHeight - line.getBoundingClientRect().height) / 2;
    }
  }, [matches, currentMatchIndex, isOpen, searchNavigation]);

  useLayoutEffect(() => {
    if (isOpen && autoScroll && followTailRef.current) scrollToBottom();
  }, [filteredLogs, isOpen, autoScroll, height, scrollToBottom]);

  // Stable row identities let browser scroll anchoring preserve the text being
  // read when the stream's bounded buffer removes old rows from its beginning.
  const logRows = useMemo(() => {
    const occurrences = new Map<string, number>();
    return filteredLogs.map((text) => {
      const occurrence = occurrences.get(text) ?? 0;
      occurrences.set(text, occurrence + 1);
      return { text, key: JSON.stringify([text, occurrence]) };
    });
  }, [filteredLogs]);

  // Detect user scroll up
  const handleScroll = () => {
    if (!isOpen || !containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 8;
    followTailRef.current = isAtBottom;
    setUserScrolledUp(!isAtBottom);
  };

  const handleResumeAutoScroll = () => {
    followTailRef.current = true;
    setUserScrolledUp(false);
    scrollToBottom();
  };

  const requestSearchNavigation = () => {
    navigateSearchRef.current = Boolean(searchTerm);
    if (searchTerm) pauseFollowing();
    setCurrentMatchIndex(-1);
  };

  const navigateMatch = (direction: number) => {
    if (!matches.length) return;
    pauseFollowing();
    navigateSearchRef.current = true;
    setSearchNavigation((previous) => previous + 1);
    setCurrentMatchIndex((previous) => (previous + direction + matches.length) % matches.length);
  };

  const handleDownloadLogs = () => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const blob = new Blob([JSON.stringify(logs, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kaiflow_log_${timestamp}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
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
          className={`kai-log-match${isFocused ? ' kai-log-match--current' : ''}`}
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
    <section
      aria-label="Backend logs"
      style={{ height: `${height}px`, display: isOpen ? 'flex' : 'none' }}
      className="kai-log-panel"
    >
      <div onMouseDown={handleMouseDown} className="kai-log-resizer" title="Drag to resize panel" />

      <header className="kai-log-header">
        <div className="kai-log-heading">
          <Terminal size={16} aria-hidden="true" />
          <h2>Backend logs</h2>
          <span className={`kai-log-status${isConnected ? ' kai-log-status--connected' : ''}`}>
            <span aria-hidden="true" />{isConnected ? 'Connected' : 'Offline'}
          </span>
          {error && <span className="kai-log-error">Connection error</span>}
        </div>
        <div className="kai-log-search-controls">
          <div className="kai-log-search">
            <Search size={15} aria-hidden="true" />
            <input
              type="text"
              aria-label="Search logs"
              placeholder="Search..."
              value={searchTerm}
              onChange={(event) => {
                const value = event.target.value;
                navigateSearchRef.current = Boolean(value);
                if (value) pauseFollowing();
                setSearchTerm(value);
                setCurrentMatchIndex(-1);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  navigateMatch(event.shiftKey ? -1 : 1);
                }
              }}
            />
            <div className="kai-log-search-options">
              {[
                { label: 'Aa', title: 'Match Case (Aa)', active: matchCase, toggle: () => setMatchCase(!matchCase) },
                { label: '\\b', title: 'Match Whole Word (\\b)', active: wholeWords, toggle: () => setWholeWords(!wholeWords) },
                { label: '.*', title: 'Use Regular Expression (.*)', active: useRegex, toggle: () => setUseRegex(!useRegex) },
              ].map((option) => (
                <button key={option.label} type="button" title={option.title} aria-label={option.title} aria-pressed={option.active} onClick={() => {
                  requestSearchNavigation();
                  option.toggle();
                }}>{option.label}</button>
              ))}
            </div>
          </div>
          {searchTerm && <div className="kai-log-match-navigation">
            <span>{matches.length ? `${currentMatchIndex + 1} of ${matches.length}` : '0 of 0'}</span>
            <button type="button" className="kai-log-icon-button" title="Previous Match" aria-label="Previous Match" disabled={!matches.length} onClick={() => navigateMatch(-1)}><ChevronUp size={16} /></button>
            <button type="button" className="kai-log-icon-button" title="Next Match" aria-label="Next Match" disabled={!matches.length} onClick={() => navigateMatch(1)}><ChevronDown size={16} /></button>
          </div>}
        </div>
        <div className="kai-log-actions" aria-label="Log actions">
          <div className="kai-log-levels" role="group" aria-label="Log level">
            {['ALL', 'INFO', 'WARNING', 'ERROR', 'DEBUG'].map((level) => (
              <button key={level} type="button" aria-pressed={levelFilter === level} onClick={() => setLevelFilter(level)}>
                {level === 'ALL' ? 'All' : level.charAt(0) + level.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
          <button type="button" className="kai-log-icon-button" title="Scroll to Top" aria-label="Scroll to Top" onClick={() => {
            pauseFollowing();
            if (containerRef.current) containerRef.current.scrollTop = 0;
          }}><ArrowUp size={16} /></button>
          <button type="button" className="kai-log-icon-button" title="Scroll to Bottom" aria-label="Scroll to Bottom" onClick={handleResumeAutoScroll}><ArrowDown size={16} /></button>
          <button type="button" className="kai-log-icon-button" title="Download Logs" aria-label="Download Logs" onClick={handleDownloadLogs}><Download size={16} /></button>
          <button type="button" className="kai-log-icon-button kai-delete-trigger" title="Clear Console" aria-label="Clear Console" onClick={clearLogs}><Trash2 size={16} /></button>
          <button
            type="button"
            className="kai-log-follow"
            aria-pressed={autoScroll}
            title="Auto-scroll to bottom on new logs"
            onClick={() => {
              const next = !autoScroll;
              setAutoScroll(next);
              if (next) handleResumeAutoScroll();
            }}
          >Auto-Scroll</button>
          <span className="kai-log-divider" aria-hidden="true" />
          <button type="button" className="kai-log-icon-button" title="Hide logs panel" aria-label="Hide logs panel" onClick={onClose}><X size={16} /></button>
        </div>
      </header>

      <div className="kai-log-body">
        <div
          ref={containerRef}
          role="log"
          aria-label="Log output"
          aria-live="off"
          tabIndex={0}
          onScroll={handleScroll}
          onWheel={(event) => { if (event.deltaY < 0) pauseFollowing(); }}
          onKeyDown={(event) => { if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) pauseFollowing(); }}
          className="kai-log-viewport"
        >
          {logRows.length === 0 ? (
            <div className="kai-log-empty">No logs found</div>
          ) : logRows.map((row, index) => (
            <div key={row.key} data-log-line={index} className="kai-log-line">
              {renderLogLine(row.text, index)}
            </div>
          ))}
        </div>
        {userScrolledUp && autoScroll && filteredLogs.length > 0 && (
          <button type="button" onClick={handleResumeAutoScroll} className="kai-log-resume">
            <ChevronDown size={15} />Resume Auto-scroll
          </button>
        )}
      </div>
    </section>
  );
}
