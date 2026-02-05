import React from 'react';

// Actions
import Activity from './actions/activity.svg?react';
import Loader from './actions/loader.svg?react';
import Loader2 from './actions/loader2.svg?react';
import Pause from './actions/pause.svg?react';
import Play from './actions/play.svg?react';
import Power from './actions/power.svg?react';
import PowerOff from './actions/power-off.svg?react';
import RefreshCcw from './actions/refresh-ccw.svg?react';
import RefreshCw from './actions/refresh-cw.svg?react';
import Rocket from './actions/rocket.svg?react';
import RotateCcw from './actions/rotate-ccw.svg?react';
import Save from './actions/save.svg?react';
import Send from './actions/send.svg?react';
import Sparkles from './actions/sparkles.svg?react';
import StopCircle from './actions/stop_circle.svg?react';
import Target from './actions/target.svg?react';
import Zap from './actions/zap.svg?react';

// Communication
import Bot from './communication/bot.svg?react';
import Mail from './communication/mail.svg?react';
import MessageCircle from './communication/message-circle.svg?react';
import MessageSquare from './communication/message-square.svg?react';
import Quote from './communication/quote.svg?react';

// File
import Archive from './file/archive.svg?react';
import Code from './file/code.svg?react';
import Database from './file/database.svg?react';
import FileInput from './file/file-input.svg?react';
import FileStack from './file/file-stack.svg?react';
import FileText from './file/file-text.svg?react';
import FileUp from './file/file-up.svg?react';
import Package from './file/package.svg?react';
import Scissors from './file/scissors.svg?react';
import Table from './file/table.svg?react';
import Terminal from './file/terminal.svg?react';
import Type from './file/type.svg?react';

// Misc
import BookOpen from './misc/book-open.svg?react';
import Box from './misc/box.svg?react';
import ChartColumn from './misc/chart-column.svg?react';
import ChartNoAxesColumn from './misc/chart-no-axes-column.svg?react';
import Cloud from './misc/cloud.svg?react';
import Condition from './misc/condition.svg?react';
import GitBranch from './misc/git-branch.svg?react';
import GitCompare from './misc/git-compare.svg?react';
import Globe from './misc/globe.svg?react';
import Lightbulb from './misc/lightbulb.svg?react';
import Network from './misc/network.svg?react';
import Pickaxe from './misc/pickaxe.svg?react';
import Tag from './misc/tag.svg?react';
import TrendingUp from './misc/trending-up.svg?react';

// Navigation
import Flag from './navigation/flag.svg?react';
import Home from './navigation/home.svg?react';
import Link from './navigation/link.svg?react';
import Settings from './navigation/settings.svg?react';

// Providers
import Cohere from './providers/cohere.svg?react';
import Openai from './providers/openai.svg?react';
import PostgresqlVectorstore from './providers/postgresql_vectorstore.svg?react';
import Redis from './providers/redis.svg?react';
import TavilySearch from './providers/tavily_search.svg?react';
import TavilyNonbrand from './providers/tavily-nonbrand.svg?react';
import Webhook from './providers/webhook.svg?react';
import WebhookFlow from './providers/webhook-flow.svg?react';

// Social Interaction
import Heart from './social_interaction/heart.svg?react';
import HeartOff from './social_interaction/heart-off.svg?react';
import Key from './social_interaction/key.svg?react';
import Lock from './social_interaction/lock.svg?react';
import Star from './social_interaction/star.svg?react';
import User from './social_interaction/user.svg?react';
import Users from './social_interaction/users.svg?react';

// Status
import Bug from './status/bug.svg?react';
import CircleAlert from './status/circle-alert.svg?react';
import CircleCheck from './status/circle-check.svg?react';
import Info from './status/info.svg?react';
import Shield from './status/shield.svg?react';
import TriangleAlert from './status/triangle-alert.svg?react';

// Theme
import Moon from './theme/moon.svg?react';
import Sun from './theme/sun.svg?react';

// Time
import Calendar from './time/calendar.svg?react';
import CalendarDays from './time/calendar-days.svg?react';
import Clock from './time/clock.svg?react';
import History from './time/history.svg?react';
import Timer from './time/timer.svg?react';

// UI Elements s
import ArrowLeft from './ui_elements/arrow-left.svg?react';
import ArrowRight from './ui_elements/arrow-right.svg?react';
import Check from './ui_elements/check.svg?react';
import CheckSquare from './ui_elements/check_square.svg?react';
import ChevronDown from './ui_elements/chevron-down.svg?react';
import ChevronLeft from './ui_elements/chevron-left.svg?react';
import ChevronRight from './ui_elements/chevron-right.svg?react';
import ChevronUp from './ui_elements/chevron-up.svg?react';
import Copy from './ui_elements/copy.svg?react';
import Download from './ui_elements/download.svg?react';
import Edit from './ui_elements/edit.svg?react';
import Eraser from './ui_elements/eraser.svg?react';
import ExternalLink from './ui_elements/external-link.svg?react';
import Eye from './ui_elements/eye.svg?react';
import Filter from './ui_elements/filter.svg?react';
import Grid from './ui_elements/grid.svg?react';
import Hash from './ui_elements/hash.svg?react';
import List from './ui_elements/list.svg?react';
import LogOut from './ui_elements/log-out.svg?react';
import Maximize2 from './ui_elements/maximize-2.svg?react';
import Minimize2 from './ui_elements/minimize-2.svg?react';
import Minus from './ui_elements/minus.svg?react';
import Pencil from './ui_elements/pencil.svg?react';
import Plus from './ui_elements/plus.svg?react';
import Search from './ui_elements/search.svg?react';
import Square from './ui_elements/square.svg?react';
import ToggleLeft from './ui_elements/toggle-left.svg?react';
import ToggleRight from './ui_elements/toggle-right.svg?react';
import Trash from './ui_elements/trash.svg?react';
import Trash2 from './ui_elements/trash-2.svg?react';
import X from './ui_elements/x.svg?react';

// Icon name-to-component map for dynamic <Icon name="..." /> usage
const iconMap: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
    Activity, Loader, Loader2, Pause, Play, Power, PowerOff,
    RefreshCcw, RefreshCw, Rocket, RotateCcw, Save, Send,
    Sparkles, StopCircle, Target, Zap,
    Bot, Mail, MessageCircle, MessageSquare, Quote,
    Archive, Code, Database, FileInput, FileStack, FileText,
    FileUp, Package, Scissors, Table, Terminal, Type,
    BookOpen, Box, ChartColumn, ChartNoAxesColumn, Cloud, Condition,
    GitBranch, GitCompare, Globe, Lightbulb, Network, Pickaxe, Tag, TrendingUp,
    Flag, Home, Link, Settings,
    Cohere, Openai, PostgresqlVectorstore, Redis,
    TavilySearch, TavilyNonbrand, Webhook, WebhookFlow,
    Heart, HeartOff, Key, Lock, Star, User, Users,
    Bug, CircleAlert, CircleCheck, Info, Shield, TriangleAlert,
    Moon, Sun,
    Calendar, CalendarDays, Clock, History, Timer,
    ArrowLeft, ArrowRight, Check, CheckSquare, ChevronDown,
    ChevronLeft, ChevronRight, ChevronUp, Copy, Download,
    Edit, Eraser, ExternalLink, Eye, Filter, Grid, Hash,
    List, LogOut, Maximize2, Minimize2, Minus, Pencil, Plus,
    Search, Square, ToggleLeft, ToggleRight, Trash, Trash2, X,
    // Service ID aliases for credentials
    openai: Openai,
    cohere: Cohere,
    postgresql_vectorstore: PostgresqlVectorstore,
    tavily_search: TavilyNonbrand,
    basic_auth: Key,
    header_auth: Lock,
    // Kebab-case aliases for backend icon names
    "file-input": FileInput,
    "file-stack": FileStack,
    "file-text": FileText,
    "file-up": FileUp,
    "book-open": BookOpen,
    "chart-column": ChartColumn,
    "chart-no-axes-column": ChartNoAxesColumn,
    "git-branch": GitBranch,
    "git-compare": GitCompare,
    "message-circle": MessageCircle,
    "message-square": MessageSquare,
    "refresh-ccw": RefreshCcw,
    "refresh-cw": RefreshCw,
    "rotate-ccw": RotateCcw,
    "stop-circle": StopCircle,
    "power-off": PowerOff,
    "circle-alert": CircleAlert,
    "circle-check": CircleCheck,
    "triangle-alert": TriangleAlert,
    "heart-off": HeartOff,
    "calendar-days": CalendarDays,
    "arrow-left": ArrowLeft,
    "arrow-right": ArrowRight,
    "check-square": CheckSquare,
    "chevron-down": ChevronDown,
    "chevron-left": ChevronLeft,
    "chevron-right": ChevronRight,
    "chevron-up": ChevronUp,
    "external-link": ExternalLink,
    "log-out": LogOut,
    "maximize-2": Maximize2,
    "minimize-2": Minimize2,
    "toggle-left": ToggleLeft,
    "toggle-right": ToggleRight,
    "trash-2": Trash2,
    "trending-up": TrendingUp,
    "webhook-flow": WebhookFlow,
    "tavily-nonbrand": TavilyNonbrand,
};

// Case-insensitive lookup
const iconMapLower: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {};
for (const [key, value] of Object.entries(iconMap)) {
    iconMapLower[key.toLowerCase()] = value;
}

interface IconProps extends React.SVGProps<SVGSVGElement> {
    name: string;
    size?: number;
}

const Icon: React.FC<IconProps> = ({ name, size, ...props }) => {
    const Component = iconMap[name] || iconMapLower[name.toLowerCase()];
    if (!Component) return null;
    if (size) {
        props.width = props.width ?? size;
        props.height = props.height ?? size;
    }
    return React.createElement(Component, props);
};

// Export all icons
export {
    Icon,
    // Actions
    Activity,
    Loader,
    Loader2,
    Pause,
    Play,
    Power,
    PowerOff,
    RefreshCcw,
    RefreshCw,
    Rocket,
    RotateCcw,
    Save,
    Send,
    Sparkles,
    StopCircle,
    Target,
    Zap,

    // Communication
    Bot,
    Mail,
    MessageCircle,
    MessageSquare,
    Quote,

    // File
    Archive,
    Code,
    Database,
    FileInput,
    FileStack,
    FileText,
    FileUp,
    Package,
    Scissors,
    Table,
    Terminal,
    Type,

    // Misc
    BookOpen,
    Box,
    ChartColumn,
    ChartNoAxesColumn,
    Cloud,
    Condition,
    GitBranch,
    GitCompare,
    Globe,
    Lightbulb,
    Network,
    Pickaxe,
    Tag,
    TrendingUp,

    // Navigation
    Flag,
    Home,
    Link,
    Settings,

    // Providers
    Cohere,
    Openai,
    PostgresqlVectorstore,
    Redis,
    TavilySearch,
    TavilyNonbrand,
    Webhook,
    WebhookFlow,

    // Social Interaction
    Heart,
    HeartOff,
    Key,
    Lock,
    Star,
    User,
    Users,

    // Status
    Bug,
    CircleAlert,
    CircleCheck,
    Info,
    Shield,
    TriangleAlert,

    // Theme
    Moon,
    Sun,

    // Time
    Calendar,
    CalendarDays,
    Clock,
    History,
    Timer,

    // UI Elements
    ArrowLeft,
    ArrowRight,
    Check,
    CheckSquare,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    ChevronUp,
    Copy,
    Download,
    Edit,
    Eraser,
    ExternalLink,
    Eye,
    Filter,
    Grid,
    Hash,
    List,
    LogOut,
    Maximize2,
    Minimize2,
    Minus,
    Pencil,
    Plus,
    Search,
    Square,
    ToggleLeft,
    ToggleRight,
    Trash,
    Trash2,
    X,

    // Backward-compatible aliases
    CircleAlert as AlertCircle,
    CircleCheck as CheckCircle,
    TriangleAlert as AlertTriangle,
    ChartColumn as BarChart2,
    Box as Store,
    Info as Bell,
};
