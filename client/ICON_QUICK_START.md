# Icon System - Quick Start ⚡

## 🚀 Hızlı Kullanım

### 1. Base State (Varsayılan)
```tsx
<Icon name="activity" />
```
Orijinal SVG özelliklerini korur.

### 2. Props ile Override
```tsx
<Icon
  name="rocket"
  size={32}              // Boyut
  color="#3b82f6"        // Renk
  strokeWidth={2.5}      // Çizgi kalınlığı
  className="hover:opacity-70"
/>
```

### 3. Named Exports
```tsx
import { Heart, Rocket, Check } from '~/components/common/Icon';

<Heart size={24} color="#ef4444" />
```

---

## 📁 Yeni Icon Ekleme

### 1. SVG'yi Kopyala
```bash
client/public/icons/actions/my-icon.svg
```

### 2. Mapping'e Ekle (`Icon.tsx`)
```tsx
const iconPaths = {
  "my-icon": "icons/actions/my-icon.svg",
};
```

### 3. Kullan!
```tsx
<Icon name="my-icon" size={24} />
```

---

## 🎨 Örnekler

### Button
```tsx
<button className="flex items-center gap-2">
  <Icon name="rocket" size={20} color="white" />
  Launch
</button>
```

### Status
```tsx
<div className="flex items-center gap-2">
  <Icon name="circle-check" color="#10b981" />
  <span>Success!</span>
</div>
```

### Loading
```tsx
<Icon name="loader" className="animate-spin" />
```

### Theme Toggle
```tsx
<Icon name="sun" className="text-yellow-500" />
<Icon name="moon" className="text-gray-700" />
```

---

## 🎯 Props

| Prop | Type | Default | Açıklama |
|------|------|---------|----------|
| `name` | `string` | **required** | Icon dosya adı |
| `size` | `number` | `16` | Boyut (px) |
| `color` | `string` | `"currentColor"` | CSS renk değeri |
| `strokeWidth` | `number \| string` | `undefined` | Çizgi kalınlığı |
| `className` | `string` | `""` | CSS class'ları |

---

## 🔗 Linkler

- **Detaylı Dokümantasyon**: `ICON_USAGE_GUIDE.md`
- **Demo Component**: `components/common/IconShowcase.tsx`
- **Icon Kaynağı**: [Lucide Icons](https://lucide.dev/icons)

---

## ✅ Checklist

- [x] Base state: SVG'yi orijinal haliyle render et
- [x] Dynamic override: Props ile özelleştirme
- [x] Mimari: `public/icons/` + mapping sistemi
- [x] Performance: Cache + lazy loading
- [x] Type-safe: Full TypeScript support
- [x] Erişilebilir: ARIA + semantic HTML

---

**💡 Tip**: `IconShowcase` component'ini import edip test edin:
```tsx
import IconShowcase from '~/components/common/IconShowcase';

<IconShowcase />
```
