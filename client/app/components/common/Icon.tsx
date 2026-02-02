import React, { useState, useEffect, useMemo } from "react";
import { resolveIconPath } from "~/lib/iconUtils";

interface IconProps {
  name: string;
  className?: string;
  size?: number;
  alt?: string;
}

// Global SVG content cache
const svgCache = new Map<string, string>();
// Dedup in-flight fetches
const fetchPromises = new Map<string, Promise<string>>();

function loadSvg(url: string): Promise<string> {
  if (svgCache.has(url)) return Promise.resolve(svgCache.get(url)!);

  if (!fetchPromises.has(url)) {
    fetchPromises.set(
      url,
      fetch(url)
        .then((res) => res.text())
        .then((text) => {
          svgCache.set(url, text);
          fetchPromises.delete(url);
          return text;
        })
        .catch((err) => {
          fetchPromises.delete(url);
          throw err;
        })
    );
  }

  return fetchPromises.get(url)!;
}

// Map icon names to their paths in public/icons
const iconPaths: Record<string, string> = {
  // UI Elements
  plus: "icons/ui_elements/plus.svg",
  minus: "icons/ui_elements/minus.svg",
  x: "icons/ui_elements/x.svg",
  check: "icons/ui_elements/check.svg",
  "check-square": "icons/ui_elements/check_square.svg",
  square: "icons/ui_elements/square.svg",
  "chevron-left": "icons/ui_elements/chevron-left.svg",
  "chevron-right": "icons/ui_elements/chevron-right.svg",
  "chevron-down": "icons/ui_elements/chevron-down.svg",
  "arrow-left": "icons/ui_elements/arrow-left.svg",
  "arrow-right": "icons/ui_elements/arrow-right.svg",
  "maximize-2": "icons/ui_elements/maximize-2.svg",
  "minimize-2": "icons/ui_elements/minimize-2.svg",
  "external-link": "icons/ui_elements/external-link.svg",
  download: "icons/ui_elements/download.svg",
  copy: "icons/ui_elements/copy.svg",
  edit: "icons/ui_elements/edit.svg",
  pencil: "icons/ui_elements/pencil.svg",
  trash: "icons/ui_elements/trash.svg",
  "trash-2": "icons/ui_elements/trash-2.svg",
  eraser: "icons/ui_elements/eraser.svg",
  filter: "icons/ui_elements/filter.svg",
  search: "icons/ui_elements/search.svg",
  grid: "icons/ui_elements/grid.svg",
  list: "icons/ui_elements/list.svg",
  eye: "icons/ui_elements/eye.svg",
  hash: "icons/ui_elements/hash.svg",
  "toggle-left": "icons/ui_elements/toggle-left.svg",

  // Actions
  play: "icons/actions/play.svg",
  pause: "icons/actions/pause.svg",
  "stop-circle": "icons/actions/stop_circle.svg",
  power: "icons/actions/power.svg",
  "power-off": "icons/actions/power-off.svg",
  save: "icons/actions/save.svg",
  send: "icons/actions/send.svg",
  "refresh-cw": "icons/actions/refresh-cw.svg",
  "refresh-ccw": "icons/actions/refresh-ccw.svg",
  "rotate-ccw": "icons/actions/rotate-ccw.svg",
  loader: "icons/actions/loader.svg",
  loader2: "icons/actions/loader2.svg",
  zap: "icons/actions/zap.svg",
  rocket: "icons/actions/rocket.svg",
  activity: "icons/actions/activity.svg",
  target: "icons/actions/target.svg",
  sparkles: "icons/actions/sparkles.svg",

  // Time
  clock: "icons/time/clock.svg",
  timer: "icons/time/timer.svg",
  calendar: "icons/time/calendar.svg",
  "calendar-days": "icons/time/calendar-days.svg",
  history: "icons/time/history.svg",

  // Theme
  sun: "icons/theme/sun.svg",
  moon: "icons/theme/moon.svg",

  // Communication
  "message-circle": "icons/communication/message-circle.svg",
  "message-square": "icons/communication/message-square.svg",
  mail: "icons/communication/mail.svg",
  quote: "icons/communication/quote.svg",
  bot: "icons/communication/bot.svg",
  users: "icons/social_interaction/users.svg",

  // Status
  info: "icons/status/info.svg",
  "circle-alert": "icons/status/circle-alert.svg",
  "alert-circle": "icons/status/circle-alert.svg", // alias
  "circle-check": "icons/status/circle-check.svg",
  "triangle-alert": "icons/status/triangle-alert.svg",
  "alert-triangle": "icons/status/triangle-alert.svg", // alias
  bug: "icons/status/bug.svg",
  shield: "icons/status/shield.svg",

  // Social Interaction
  heart: "icons/social_interaction/heart.svg",
  "heart-off": "icons/social_interaction/heart-off.svg",
  star: "icons/social_interaction/star.svg",
  user: "icons/social_interaction/user.svg",
  key: "icons/social_interaction/key.svg",
  lock: "icons/social_interaction/lock.svg",

  // Navigation
  home: "icons/navigation/home.svg",
  settings: "icons/navigation/settings.svg",
  flag: "icons/navigation/flag.svg",
  link: "icons/navigation/link.svg",

  // File
  "file-text": "icons/file/file-text.svg",
  "file-up": "icons/file/file-up.svg",
  "file-input": "icons/file/file-input.svg",
  "file-stack": "icons/file/file-stack.svg",
  database: "icons/file/database.svg",
  table: "icons/file/table.svg",
  code: "icons/file/code.svg",
  terminal: "icons/file/terminal.svg",
  archive: "icons/file/archive.svg",
  package: "icons/file/package.svg",
  scissors: "icons/file/scissors.svg",
  type: "icons/file/type.svg",

  // Providers
  openai: "icons/providers/openai.svg",
  cohere: "icons/providers/cohere.svg",
  redis: "icons/providers/redis.svg",
  postgresql: "icons/providers/postgresql_vectorstore.svg",
  postgresql_vectorstore: "icons/providers/postgresql_vectorstore.svg", // Alias for credentials
  tavily: "icons/providers/tavily-nonbrand.svg",
  tavily_search: "icons/providers/tavily-nonbrand.svg", // Alias for credentials
  webhook: "icons/providers/webhook.svg",

  // Auth types (aliased to globe/lock if needed, or specific icons)
  basic_auth: "icons/social_interaction/key.svg",
  header_auth: "icons/data/code.svg",

  // Misc
  box: "icons/misc/box.svg",
  globe: "icons/misc/globe.svg",
  cloud: "icons/misc/cloud.svg",
  lightbulb: "icons/misc/lightbulb.svg",
  tag: "icons/misc/tag.svg",
  "book-open": "icons/misc/book-open.svg",
  "trending-up": "icons/misc/trending-up.svg",
  "git-branch": "icons/misc/git-branch.svg",
  "git-compare": "icons/misc/git-compare.svg",
  condition: "icons/misc/condition.svg",
  network: "icons/misc/network.svg",
  pickaxe: "icons/misc/pickaxe.svg",
  "chart-column": "icons/misc/chart-column.svg",

  // Fallbacks
  "bar-chart-2": "icons/misc/chart-column.svg",
  bell: "icons/status/info.svg", // fallback
  store: "icons/file/package.svg", // fallback
  "log-out": "icons/actions/power-off.svg", // fallback
  "toggle-right": "icons/theme/toggle-left.svg", // fallback
};

function getIconPath(name: string): string | undefined {
  let iconPath = iconPaths[name.toLowerCase()];
  if (!iconPath) {
    const normalizedName = name.toLowerCase().replace(/-/g, "");
    const foundKey = Object.keys(iconPaths).find(
      (k) => k.replace(/-/g, "") === normalizedName
    );
    if (foundKey) {
      iconPath = iconPaths[foundKey];
    }
  }
  return iconPath;
}

export default function Icon({ name, className = "", size = 16, alt }: IconProps) {
  const iconPath = getIconPath(name);
  const resolvedPath = iconPath ? resolveIconPath(iconPath) : undefined;

  // Initialize from cache synchronously to avoid flicker
  const [svgContent, setSvgContent] = useState<string | null>(
    resolvedPath && svgCache.has(resolvedPath)
      ? svgCache.get(resolvedPath)!
      : null
  );

  useEffect(() => {
    if (!resolvedPath) return;

    if (svgCache.has(resolvedPath)) {
      setSvgContent(svgCache.get(resolvedPath)!);
      return;
    }

    let cancelled = false;
    loadSvg(resolvedPath)
      .then((text) => {
        if (!cancelled) setSvgContent(text);
      })
      .catch((err) => {
        console.warn(`Failed to load icon "${name}":`, err);
      });

    return () => {
      cancelled = true;
    };
  }, [resolvedPath, name]);

  // Process SVG: inject className and size into the <svg> element
  const processedSvg = useMemo(() => {
    if (!svgContent) return null;
    return svgContent.replace(/<svg([^>]*)>/, (_, attrs) => {
      const cleanAttrs = attrs
        .replace(/\s*width="[^"]*"/g, "")
        .replace(/\s*height="[^"]*"/g, "")
        .replace(/\s*class="[^"]*"/g, "");
      return `<svg${cleanAttrs} width="${size}" height="${size}" class="inline-block ${className}">`;
    });
  }, [svgContent, size, className]);

  if (!resolvedPath) {
    console.warn(`Icon "${name}" not found in icon paths`);
    return null;
  }

  if (!processedSvg) return null;

  return (
    <span
      dangerouslySetInnerHTML={{ __html: processedSvg }}
      style={{ display: "contents" }}
    />
  );
}

// Named exports for commonly used icons (for easier migration)
export const MessageSquare = (props: Omit<IconProps, "name">) => <Icon name="message-square" {...props} />;
export const Minimize2 = (props: Omit<IconProps, "name">) => <Icon name="minimize-2" {...props} />;
export const Maximize2 = (props: Omit<IconProps, "name">) => <Icon name="maximize-2" {...props} />;
export const History = (props: Omit<IconProps, "name">) => <Icon name="history" {...props} />;
export const Eraser = (props: Omit<IconProps, "name">) => <Icon name="eraser" {...props} />;
export const Plus = (props: Omit<IconProps, "name">) => <Icon name="plus" {...props} />;
export const Minus = (props: Omit<IconProps, "name">) => <Icon name="minus" {...props} />;
export const Heart = (props: Omit<IconProps, "name">) => <Icon name="heart" {...props} />;
export const HeartOff = (props: Omit<IconProps, "name">) => <Icon name="heart-off" {...props} />;
export const Clock = (props: Omit<IconProps, "name">) => <Icon name="clock" {...props} />;
export const Trash = (props: Omit<IconProps, "name">) => <Icon name="trash" {...props} />;
export const Trash2 = (props: Omit<IconProps, "name">) => <Icon name="trash-2" {...props} />;
export const AlertTriangle = (props: Omit<IconProps, "name">) => <Icon name="alert-triangle" {...props} />;
export const AlertCircle = (props: Omit<IconProps, "name">) => <Icon name="alert-circle" {...props} />;
export const Bug = (props: Omit<IconProps, "name">) => <Icon name="bug" {...props} />;
export const Zap = (props: Omit<IconProps, "name">) => <Icon name="zap" {...props} />;
export const RefreshCw = (props: Omit<IconProps, "name">) => <Icon name="refresh-cw" {...props} />;
export const Info = (props: Omit<IconProps, "name">) => <Icon name="info" {...props} />;
export const X = (props: Omit<IconProps, "name">) => <Icon name="x" {...props} />;

// UI Elements
export const ArrowLeft = (props: Omit<IconProps, "name">) => <Icon name="arrow-left" {...props} />;
export const ArrowRight = (props: Omit<IconProps, "name">) => <Icon name="arrow-right" {...props} />;
export const ChevronUp = (props: Omit<IconProps, "name">) => <Icon name="chevron-up" {...props} />;
export const ChevronDown = (props: Omit<IconProps, "name">) => <Icon name="chevron-down" {...props} />;
export const ChevronLeft = (props: Omit<IconProps, "name">) => <Icon name="chevron-left" {...props} />;
export const ChevronRight = (props: Omit<IconProps, "name">) => <Icon name="chevron-right" {...props} />;
export const ExternalLink = (props: Omit<IconProps, "name">) => <Icon name="external-link" {...props} />;
export const Download = (props: Omit<IconProps, "name">) => <Icon name="download" {...props} />;
export const Copy = (props: Omit<IconProps, "name">) => <Icon name="copy" {...props} />;
export const Edit = (props: Omit<IconProps, "name">) => <Icon name="edit" {...props} />;
export const Search = (props: Omit<IconProps, "name">) => <Icon name="search" {...props} />;
export const Hash = (props: Omit<IconProps, "name">) => <Icon name="hash" {...props} />;
export const Check = (props: Omit<IconProps, "name">) => <Icon name="check" {...props} />;
export const CheckCircle = (props: Omit<IconProps, "name">) => <Icon name="circle-check" {...props} />;

// Actions
export const Play = (props: Omit<IconProps, "name">) => <Icon name="play" {...props} />;
export const Power = (props: Omit<IconProps, "name">) => <Icon name="power" {...props} />;
export const PowerOff = (props: Omit<IconProps, "name">) => <Icon name="power-off" {...props} />;
export const Save = (props: Omit<IconProps, "name">) => <Icon name="save" {...props} />;
export const Loader = (props: Omit<IconProps, "name">) => <Icon name="loader" {...props} />;
export const Sparkles = (props: Omit<IconProps, "name">) => <Icon name="sparkles" {...props} />;

// Theme
export const Sun = (props: Omit<IconProps, "name">) => <Icon name="sun" {...props} />;
export const Moon = (props: Omit<IconProps, "name">) => <Icon name="moon" {...props} />;

// Communication
export const Bot = (props: Omit<IconProps, "name">) => <Icon name="bot" {...props} />;
export const Quote = (props: Omit<IconProps, "name">) => <Icon name="quote" {...props} />;
export const Mail = (props: Omit<IconProps, "name">) => <Icon name="mail" {...props} />;

// Navigation
export const Settings = (props: Omit<IconProps, "name">) => <Icon name="settings" {...props} />;
export const Home = (props: Omit<IconProps, "name">) => <Icon name="home" {...props} />;

// File
export const FileText = (props: Omit<IconProps, "name">) => <Icon name="file-text" {...props} />;
export const FileUp = (props: Omit<IconProps, "name">) => <Icon name="file-up" {...props} />;
export const Database = (props: Omit<IconProps, "name">) => <Icon name="database" {...props} />;
export const Terminal = (props: Omit<IconProps, "name">) => <Icon name="terminal" {...props} />;
export const Code = (props: Omit<IconProps, "name">) => <Icon name="code" {...props} />;
export const Table = (props: Omit<IconProps, "name">) => <Icon name="table" {...props} />;

// Social
export const User = (props: Omit<IconProps, "name">) => <Icon name="user" {...props} />;
export const Key = (props: Omit<IconProps, "name">) => <Icon name="key" {...props} />;

// Misc
export const Box = (props: Omit<IconProps, "name">) => <Icon name="box" {...props} />;
export const Globe = (props: Omit<IconProps, "name">) => <Icon name="globe" {...props} />;
export const Calendar = (props: Omit<IconProps, "name">) => <Icon name="calendar" {...props} />;
export const Pencil = (props: Omit<IconProps, "name">) => <Icon name="pencil" {...props} />;
export const Loader2 = (props: Omit<IconProps, "name">) => <Icon name="loader2" {...props} />;
export const BarChart2 = (props: Omit<IconProps, "name">) => <Icon name="bar-chart-2" {...props} />;
export const Store = (props: Omit<IconProps, "name">) => <Icon name="store" {...props} />;
export const LogOut = (props: Omit<IconProps, "name">) => <Icon name="log-out" {...props} />;
export const Bell = (props: Omit<IconProps, "name">) => <Icon name="bell" {...props} />;
export const TrendingUp = (props: Omit<IconProps, "name">) => <Icon name="trending-up" {...props} />;
export const Activity = (props: Omit<IconProps, "name">) => <Icon name="activity" {...props} />;
export const Package = (props: Omit<IconProps, "name">) => <Icon name="package" {...props} />;
export const Lock = (props: Omit<IconProps, "name">) => <Icon name="lock" {...props} />;
export const Square = (props: Omit<IconProps, "name">) => <Icon name="square" {...props} />;
export const CheckSquare = (props: Omit<IconProps, "name">) => <Icon name="check-square" {...props} />;
export const ToggleLeft = (props: Omit<IconProps, "name">) => <Icon name="toggle-left" {...props} />;
export const ToggleRight = (props: Omit<IconProps, "name">) => <Icon name="toggle-right" {...props} />;
export const Eye = (props: Omit<IconProps, "name">) => <Icon name="eye" {...props} />;
export const MessageCircle = (props: Omit<IconProps, "name">) => <Icon name="message-circle" {...props} />;
export const Send = (props: Omit<IconProps, "name">) => <Icon name="send" {...props} />;

// Node-specific icons
export const Rocket = (props: Omit<IconProps, "name">) => <Icon name="rocket" {...props} />;
export const Timer = (props: Omit<IconProps, "name">) => <Icon name="timer" {...props} />;
export const StopCircle = (props: Omit<IconProps, "name">) => <Icon name="stop-circle" {...props} />;
export const Pause = (props: Omit<IconProps, "name">) => <Icon name="pause" {...props} />;
export const Grid = (props: Omit<IconProps, "name">) => <Icon name="grid" {...props} />;
export const List = (props: Omit<IconProps, "name">) => <Icon name="list" {...props} />;
export const Star = (props: Omit<IconProps, "name">) => <Icon name="star" {...props} />;
export const Users = (props: Omit<IconProps, "name">) => <Icon name="users" {...props} />;
export const Filter = (props: Omit<IconProps, "name">) => <Icon name="filter" {...props} />;
export const Shield = (props: Omit<IconProps, "name">) => <Icon name="shield" {...props} />;
export const Cloud = (props: Omit<IconProps, "name">) => <Icon name="cloud" {...props} />;
export const Tag = (props: Omit<IconProps, "name">) => <Icon name="tag" {...props} />;
export const RotateCcw = (props: Omit<IconProps, "name">) => <Icon name="rotate-ccw" {...props} />;
export const Lightbulb = (props: Omit<IconProps, "name">) => <Icon name="lightbulb" {...props} />;
export const RefreshCcw = (props: Omit<IconProps, "name">) => <Icon name="refresh-ccw" {...props} />;
export const BookOpen = (props: Omit<IconProps, "name">) => <Icon name="book-open" {...props} />;
export const Flag = (props: Omit<IconProps, "name">) => <Icon name="flag" {...props} />;
export const Target = (props: Omit<IconProps, "name">) => <Icon name="target" {...props} />;
export const CalendarDays = (props: Omit<IconProps, "name">) => <Icon name="calendar-days" {...props} />;
