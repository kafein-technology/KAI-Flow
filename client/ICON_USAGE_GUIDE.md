# Icon Component Kullanım Kılavuzu

Bu rehber, projenizdeki dinamik SVG icon sisteminin nasıl kullanılacağını açıklar.

## Mimari

### 📁 Dosya Yapısı
```
client/
├── public/
│   └── icons/               # Ham SVG dosyalarınız buraya
│       ├── actions/
│       ├── communication/
│       ├── file/
│       ├── misc/
│       ├── navigation/
│       ├── providers/
│       ├── social_interaction/
│       ├── status/
│       ├── theme/
│       ├── time/
│       └── ui_elements/
└── app/
    └── components/
        └── common/
            └── Icon.tsx     # Base Icon component
```

### ⚙️ Nasıl Çalışır?

1. **SVG Dosyaları**: `public/icons/` klasörüne kategorize edilmiş şekilde konulur
2. **İsimlendirme**: Dosyalar kebab-case formatında (örn: `activity.svg`)
3. **Dinamik Import**: Component, SVG'leri runtime'da fetch eder ve cache'ler
4. **Override Sistemi**: Props ile SVG özellikleri üzerine yazılabilir

---

## 1️⃣ Base State (Varsayılan Kullanım)

Hiçbir prop vermediğinizde, SVG **orijinal haliyle** render edilir:

```tsx
import Icon from '~/components/common/Icon';

function MyComponent() {
  return <Icon name="activity" />;
}
```

**Render edilir:**
- Orijinal renk: `stroke="currentColor"` (parent'tan renk alır)
- Orijinal stroke-width: `2`
- Varsayılan boyut: `16px`

---

## 2️⃣ Dinamik Override

### Size (Boyut)

```tsx
<Icon name="activity" size={24} />
<Icon name="heart" size={32} />
<Icon name="settings" size={48} />
```

### Color (Renk)

```tsx
{/* Hex renk */}
<Icon name="activity" color="#3b82f6" />

{/* RGB/RGBA */}
<Icon name="heart" color="rgb(239, 68, 68)" />

{/* CSS değişkeni */}
<Icon name="check" color="var(--primary-color)" />

{/* Named color */}
<Icon name="info" color="blue" />
```

### Stroke Width

```tsx
<Icon name="activity" strokeWidth={1} />    {/* İnce çizgi */}
<Icon name="activity" strokeWidth={2.5} /> {/* Kalın çizgi */}
<Icon name="activity" strokeWidth="3" />   {/* String de olabilir */}
```

### Kombine Kullanım

```tsx
<Icon
  name="rocket"
  size={40}
  color="#8b5cf6"
  strokeWidth={2.5}
  className="hover:opacity-80 transition-opacity"
/>
```

---

## 3️⃣ TailwindCSS ile Kullanım

TailwindCSS class'larıyla tam uyumlu çalışır:

```tsx
{/* Text rengi ile */}
<Icon name="sun" className="text-yellow-500" />

{/* Hover efekti */}
<Icon
  name="heart"
  className="text-red-500 hover:text-red-700 cursor-pointer transition-colors"
/>

{/* Responsive boyut */}
<Icon
  name="menu"
  className="w-6 h-6 md:w-8 md:h-8"
/>

{/* Animasyon */}
<Icon
  name="loader"
  className="animate-spin text-blue-600"
/>
```

---

## 4️⃣ Named Exports (Kısa Yol)

Sık kullanılan icon'lar için hazır export'lar:

```tsx
import { Heart, Check, Settings, Loader } from '~/components/common/Icon';

function MyComponent() {
  return (
    <>
      <Heart size={24} color="#ef4444" />
      <Check size={20} className="text-green-600" />
      <Settings size={18} />
      <Loader className="animate-spin" />
    </>
  );
}
```

**Mevcut Named Exports:**
- UI Elements: `ArrowLeft`, `ArrowRight`, `ChevronDown`, `Check`, `Copy`, `Search`, vb.
- Actions: `Play`, `Pause`, `Power`, `Save`, `Loader`, `Sparkles`
- Communication: `Bot`, `MessageCircle`, `Mail`
- Status: `AlertTriangle`, `AlertCircle`, `Bug`, `Info`
- File: `FileText`, `Database`, `Terminal`, `Code`
- Theme: `Sun`, `Moon`
- Social: `User`, `Heart`, `Key`, `Lock`
- Navigation: `Home`, `Settings`
- Misc: `Calendar`, `Clock`, `Globe`, `Lightbulb`

---

## 5️⃣ Yeni SVG Ekleme

### Adım 1: SVG Dosyasını Ekle
Lucide.dev'den indirdiğiniz SVG'yi uygun kategoriye koyun:

```bash
client/public/icons/actions/new-icon.svg
```

### Adım 2: Icon Mapping'e Ekle
`Icon.tsx` içindeki `iconPaths` objesine ekleyin:

```tsx
const iconPaths: Record<string, string> = {
  // ...
  "new-icon": "icons/actions/new-icon.svg",
};
```

### Adım 3: Kullanın!

```tsx
<Icon name="new-icon" size={24} />
```

### (Opsiyonel) Named Export Ekle

Sık kullanacaksanız, dosyanın sonuna ekleyin:

```tsx
export const NewIcon = (props: Omit<IconProps, "name">) =>
  <Icon name="new-icon" {...props} />;
```

Kullanım:
```tsx
import { NewIcon } from '~/components/common/Icon';

<NewIcon size={24} color="#3b82f6" />
```

---

## 6️⃣ Performance İpuçları

### Cache Sistemi
Component otomatik olarak yüklenen SVG'leri cache'ler. Aynı icon birden fazla yerde kullanıldığında sadece bir kez fetch edilir.

### Lazy Loading
SVG'ler sadece kullanıldıklarında yüklenir (lazy loading).

### Memoization
SVG işleme (processing) işlemi `useMemo` ile optimize edilmiştir.

---

## 7️⃣ Gerçek Dünya Örnekleri

### Buton İçinde

```tsx
<button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
  <Icon name="rocket" size={20} color="white" />
  <span>Launch</span>
</button>
```

### Durum Göstergesi

```tsx
function StatusIndicator({ type, message }) {
  const config = {
    success: { icon: "circle-check", color: "#10b981" },
    error: { icon: "alert-circle", color: "#ef4444" },
    warning: { icon: "triangle-alert", color: "#f59e0b" },
    info: { icon: "info", color: "#3b82f6" },
  };

  const { icon, color } = config[type];

  return (
    <div className="flex items-center gap-2">
      <Icon name={icon} size={20} color={color} />
      <span>{message}</span>
    </div>
  );
}
```

### Dinamik Icon Seçimi

```tsx
function ProviderIcon({ provider, ...props }) {
  const iconMap = {
    openai: "openai",
    cohere: "cohere",
    redis: "redis",
    postgresql: "postgresql",
  };

  return <Icon name={iconMap[provider] || "globe"} {...props} />;
}

// Kullanım
<ProviderIcon provider="openai" size={32} />
```

### Loading State

```tsx
function LoadingButton({ isLoading, children }) {
  return (
    <button disabled={isLoading}>
      {isLoading ? (
        <Icon name="loader" className="animate-spin mr-2" size={16} />
      ) : (
        <Icon name="check" className="mr-2" size={16} />
      )}
      {children}
    </button>
  );
}
```

---

## 8️⃣ TypeScript Tip Desteği

Component tam TypeScript desteği ile gelir:

```tsx
interface IconProps {
  name: string;                    // Icon adı (zorunlu)
  className?: string;              // CSS class'ları
  size?: number;                   // Boyut (px)
  alt?: string;                    // Alt text (erişilebilirlik)
  color?: string;                  // Renk override
  strokeWidth?: number | string;   // Stroke genişliği override
}
```

---

## 9️⃣ Erişilebilirlik (Accessibility)

```tsx
{/* Dekoratif icon (semantik anlamı yok) */}
<Icon name="sparkles" alt="" />

{/* Anlamlı icon (screen reader için) */}
<Icon name="settings" alt="Settings" />

{/* Button içinde */}
<button aria-label="Delete item">
  <Icon name="trash" alt="" />
</button>
```

---

## 🔟 SSS (Sık Sorulan Sorular)

### S: Icon görünmüyor, ne yapmalıyım?
**C:**
1. SVG dosyasının `public/icons/` altında olduğundan emin olun
2. `iconPaths` objesine mapping eklendiğini kontrol edin
3. Console'da hata var mı bakın
4. SVG dosya adının kebab-case olduğundan emin olun

### S: currentColor nedir?
**C:** SVG'deki `stroke="currentColor"`, icon'un parent element'in `color` CSS özelliğini kullanmasını sağlar. Bu sayede TailwindCSS'in `text-*` class'ları çalışır.

### S: Fill vs Stroke?
**C:** Lucide icon'ları stroke-based'dir (çizgi). Fill kullanmak isterseniz `color` prop'unu kullandığınızda otomatik olarak `fill="none"` ayarlanır.

### S: Icon çok ağır yükleniyor?
**C:**
- SVG dosyalarını SVGO ile optimize edin
- Kritik icon'ları bundle'a dahil edin (inline)
- Cache çalıştığından emin olun

### S: Dark mode desteği?
**C:**
```tsx
<Icon
  name="sun"
  className="text-gray-900 dark:text-gray-100"
/>

{/* veya */}
<Icon
  name="moon"
  color={isDarkMode ? "#fff" : "#000"}
/>
```

---

## 🎯 Özet

✅ **Base State**: Props vermeden orijinal SVG render edilir
✅ **Dinamik Override**: `size`, `color`, `strokeWidth` props'ları ile özelleştirme
✅ **Mimari**: `public/icons/` klasöründe kategorize edilmiş SVG'ler
✅ **Performance**: Otomatik cache + lazy loading + memoization
✅ **Type-Safe**: Tam TypeScript desteği
✅ **Erişilebilir**: Semantic HTML + ARIA desteği

---

**Dokümantasyon Son Güncelleme:** 2026-02-02
**Component Versiyon:** 2.0 (Color & StrokeWidth Override)
