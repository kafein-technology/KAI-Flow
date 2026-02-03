# Icon System Kullanımı

## Genel Bakış

Tüm SVG iconlar `client/icons/` dizininde kategorilere göre organize edilmiştir ve merkezi bir index dosyası üzerinden export edilir.

## Kullanım

### Temel Kullanım

```tsx
import { SettingsIcon, DeleteIcon, UsersIcon } from '@/icons';

function MyComponent() {
  return (
    <div>
      <SettingsIcon className="w-6 h-6" />
      <DeleteIcon className="w-4 h-4 text-red-500" />
      <UsersIcon width={24} height={24} />
    </div>
  );
}
```

### SVG Props

Tüm iconlar standart React SVG props'larını destekler:

```tsx
<SettingsIcon
  className="w-5 h-5"
  fill="currentColor"
  stroke="currentColor"
  strokeWidth={2}
  onClick={() => console.log('clicked')}
/>
```

## Kategoriler

### Actions
`ActivityIcon`, `LoaderIcon`, `Loader2Icon`, `PauseIcon`, `PlayIcon`, `PowerIcon`, `PowerOffIcon`, `RefreshCcwIcon`, `RefreshCwIcon`, `RocketIcon`, `RotateCcwIcon`, `SaveIcon`, `SendIcon`, `SparklesIcon`, `StopCircleIcon`, `TargetIcon`, `ZapIcon`

### Communication
`BotIcon`, `MailIcon`, `MessageCircleIcon`, `MessageSquareIcon`, `QuoteIcon`

### File
`ArchiveIcon`, `CodeIcon`, `DatabaseIcon`, `FileInputIcon`, `FileStackIcon`, `FileTextIcon`, `FileUpIcon`, `PackageIcon`, `ScissorsIcon`, `TableIcon`, `TerminalIcon`, `TypeIcon`

### Misc
`BookOpenIcon`, `BoxIcon`, `ChartColumnIcon`, `ChartNoAxesColumnIcon`, `CloudIcon`, `ConditionIcon`, `GitBranchIcon`, `GitCompareIcon`, `GlobeIcon`, `LightbulbIcon`, `NetworkIcon`, `PickaxeIcon`, `TagIcon`, `TrendingUpIcon`

### Navigation
`FlagIcon`, `HomeIcon`, `LinkIcon`, `SettingsIcon`

### Providers
`CohereIcon`, `OpenaiIcon`, `PostgresqlVectorstoreIcon`, `RedisIcon`, `TavilySearchIcon`, `TavilyNonbrandIcon`, `WebhookIcon`, `WebhookFlowIcon`

### Social Interaction
`HeartIcon`, `HeartOffIcon`, `KeyIcon`, `LockIcon`, `StarIcon`, `UserIcon`, `UsersIcon`

### Status
`BugIcon`, `CircleAlertIcon`, `CircleCheckIcon`, `InfoIcon`, `ShieldIcon`, `TriangleAlertIcon`

### Theme
`MoonIcon`, `SunIcon`

### Time
`CalendarIcon`, `CalendarDaysIcon`, `ClockIcon`, `HistoryIcon`, `TimerIcon`

### UI Elements
`ArrowLeftIcon`, `ArrowRightIcon`, `CheckIcon`, `CheckSquareIcon`, `ChevronDownIcon`, `ChevronLeftIcon`, `ChevronRightIcon`, `ChevronUpIcon`, `CopyIcon`, `DownloadIcon`, `EditIcon`, `EraserIcon`, `ExternalLinkIcon`, `EyeIcon`, `FilterIcon`, `GridIcon`, `HashIcon`, `ListIcon`, `LogOutIcon`, `Maximize2Icon`, `Minimize2Icon`, `MinusIcon`, `PencilIcon`, `PlusIcon`, `SearchIcon`, `SquareIcon`, `ToggleLeftIcon`, `TrashIcon`, `Trash2Icon`, `XIcon`

## Yeni Icon Ekleme

1. SVG dosyasını uygun kategoriye ekleyin: `client/icons/{category}/{icon-name}.svg`
2. `client/icons/index.ts` dosyasını güncelleyin:
   ```ts
   // Import
   import NewIconIcon from './{category}/{icon-name}.svg?react';

   // Export listesine ekleyin
   export {
     // ...
     NewIconIcon,
   };
   ```

## TypeScript Desteği

SVG module declaration `client/app/types/index.d.ts` dosyasında tanımlıdır:

```ts
declare module '*.svg?react' {
    import React from 'react';
    const ReactComponent: React.FC<React.SVGProps<SVGSVGElement>>;
    export default ReactComponent;
}
```
