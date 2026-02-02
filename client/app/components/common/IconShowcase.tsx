/**
 * Icon Showcase Component
 *
 * Bu component, Icon sisteminin tüm özelliklerini gösterir.
 * Kullanım: Bu dosyayı herhangi bir route'a import edip test edebilirsiniz.
 *
 * @example
 * import IconShowcase from '~/components/common/IconShowcase';
 *
 * <IconShowcase />
 */

import React, { useState } from 'react';
import Icon, {
  Heart,
  Activity,
  Rocket,
  Settings,
  Sun,
  Moon,
  Loader,
  Check,
  AlertTriangle,
} from './Icon';

export default function IconShowcase() {
  const [color, setColor] = useState('#3b82f6');
  const [size, setSize] = useState(32);
  const [strokeWidth, setStrokeWidth] = useState(2);

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-12 bg-gray-50 min-h-screen">
      <header className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">
          Icon System Showcase
        </h1>
        <p className="text-gray-600">
          Dinamik SVG Icon Component'i - Tüm Özellikler
        </p>
      </header>

      {/* 1. Base State */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-4 text-gray-800">
          1️⃣ Base State (Varsayılan)
        </h2>
        <p className="text-gray-600 mb-4">
          Hiçbir prop vermediğinizde, SVG orijinal haliyle render edilir.
        </p>

        <div className="flex gap-6 items-center">
          <Icon name="activity" />
          <Icon name="heart" />
          <Icon name="rocket" />
          <Icon name="settings" />
          <Icon name="sun" />
        </div>

        <div className="mt-4 bg-gray-100 p-4 rounded font-mono text-sm">
          {'<Icon name="activity" />'}
        </div>
      </section>

      {/* 2. Size Override */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-4 text-gray-800">
          2️⃣ Size Override (Boyut)
        </h2>

        <div className="flex gap-6 items-end">
          <div className="text-center">
            <Icon name="heart" size={16} />
            <p className="text-xs mt-2 text-gray-500">16px</p>
          </div>
          <div className="text-center">
            <Icon name="heart" size={24} />
            <p className="text-xs mt-2 text-gray-500">24px</p>
          </div>
          <div className="text-center">
            <Icon name="heart" size={32} />
            <p className="text-xs mt-2 text-gray-500">32px</p>
          </div>
          <div className="text-center">
            <Icon name="heart" size={48} />
            <p className="text-xs mt-2 text-gray-500">48px</p>
          </div>
          <div className="text-center">
            <Icon name="heart" size={64} />
            <p className="text-xs mt-2 text-gray-500">64px</p>
          </div>
        </div>

        <div className="mt-4 bg-gray-100 p-4 rounded font-mono text-sm">
          {'<Icon name="heart" size={32} />'}
        </div>
      </section>

      {/* 3. Color Override */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-4 text-gray-800">
          3️⃣ Color Override (Renk)
        </h2>

        <div className="flex gap-6 items-center">
          <Icon name="heart" size={40} color="#ef4444" />
          <Icon name="activity" size={40} color="#3b82f6" />
          <Icon name="rocket" size={40} color="#8b5cf6" />
          <Icon name="check" size={40} color="#10b981" />
          <Icon name="sun" size={40} color="#f59e0b" />
        </div>

        <div className="mt-4 bg-gray-100 p-4 rounded font-mono text-sm">
          {'<Icon name="heart" size={40} color="#ef4444" />'}
        </div>
      </section>

      {/* 4. Stroke Width Override */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-4 text-gray-800">
          4️⃣ Stroke Width Override
        </h2>

        <div className="flex gap-6 items-center">
          <div className="text-center">
            <Icon name="activity" size={40} strokeWidth={0.5} />
            <p className="text-xs mt-2 text-gray-500">0.5</p>
          </div>
          <div className="text-center">
            <Icon name="activity" size={40} strokeWidth={1} />
            <p className="text-xs mt-2 text-gray-500">1</p>
          </div>
          <div className="text-center">
            <Icon name="activity" size={40} strokeWidth={2} />
            <p className="text-xs mt-2 text-gray-500">2 (default)</p>
          </div>
          <div className="text-center">
            <Icon name="activity" size={40} strokeWidth={3} />
            <p className="text-xs mt-2 text-gray-500">3</p>
          </div>
          <div className="text-center">
            <Icon name="activity" size={40} strokeWidth={4} />
            <p className="text-xs mt-2 text-gray-500">4</p>
          </div>
        </div>

        <div className="mt-4 bg-gray-100 p-4 rounded font-mono text-sm">
          {'<Icon name="activity" size={40} strokeWidth={3} />'}
        </div>
      </section>

      {/* 5. Kombine Kullanım */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-4 text-gray-800">
          5️⃣ Kombine Kullanım (All Props)
        </h2>

        <div className="flex gap-6 items-center">
          <Icon
            name="rocket"
            size={48}
            color="#8b5cf6"
            strokeWidth={2.5}
            className="hover:opacity-70 transition-opacity cursor-pointer"
          />
          <Icon
            name="heart"
            size={48}
            color="#ef4444"
            strokeWidth={3}
            className="animate-pulse"
          />
          <Icon
            name="activity"
            size={48}
            color="#3b82f6"
            strokeWidth={1.5}
            className="hover:scale-110 transition-transform cursor-pointer"
          />
        </div>

        <div className="mt-4 bg-gray-100 p-4 rounded font-mono text-sm overflow-x-auto">
          {`<Icon
  name="rocket"
  size={48}
  color="#8b5cf6"
  strokeWidth={2.5}
  className="hover:opacity-70 transition-opacity"
/>`}
        </div>
      </section>

      {/* 6. Interactive Demo */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-4 text-gray-800">
          6️⃣ Interactive Demo
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Controls */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Color: {color}
              </label>
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="w-full h-10 rounded cursor-pointer"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Size: {size}px
              </label>
              <input
                type="range"
                min="16"
                max="128"
                value={size}
                onChange={(e) => setSize(Number(e.target.value))}
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Stroke Width: {strokeWidth}
              </label>
              <input
                type="range"
                min="0.5"
                max="5"
                step="0.5"
                value={strokeWidth}
                onChange={(e) => setStrokeWidth(Number(e.target.value))}
                className="w-full"
              />
            </div>
          </div>

          {/* Preview */}
          <div className="flex items-center justify-center bg-gray-50 rounded-lg border-2 border-dashed border-gray-300 min-h-[200px]">
            <Icon
              name="rocket"
              size={size}
              color={color}
              strokeWidth={strokeWidth}
            />
          </div>
        </div>

        <div className="mt-4 bg-gray-100 p-4 rounded font-mono text-sm overflow-x-auto">
          {`<Icon
  name="rocket"
  size={${size}}
  color="${color}"
  strokeWidth={${strokeWidth}}
/>`}
        </div>
      </section>

      {/* 7. Named Exports */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-4 text-gray-800">
          7️⃣ Named Exports (Kısa Yol)
        </h2>

        <div className="flex gap-6 items-center">
          <Heart size={32} color="#ef4444" />
          <Activity size={32} color="#3b82f6" />
          <Rocket size={32} color="#8b5cf6" />
          <Settings size={32} color="#6b7280" />
          <Sun size={32} color="#f59e0b" />
        </div>

        <div className="mt-4 bg-gray-100 p-4 rounded font-mono text-sm">
          {`import { Heart, Activity, Rocket } from '~/components/common/Icon';

<Heart size={32} color="#ef4444" />
<Activity size={32} color="#3b82f6" />`}
        </div>
      </section>

      {/* 8. Real World Examples */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-2xl font-semibold mb-4 text-gray-800">
          8️⃣ Real World Examples
        </h2>

        <div className="space-y-6">
          {/* Button */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Button with Icon:</p>
            <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
              <Icon name="rocket" size={20} color="white" />
              <span>Launch Project</span>
            </button>
          </div>

          {/* Status Indicators */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Status Indicators:</p>
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-green-700">
                <Check size={20} color="#10b981" />
                <span>Success: Operation completed</span>
              </div>
              <div className="flex items-center gap-2 text-red-700">
                <AlertTriangle size={20} color="#ef4444" />
                <span>Error: Something went wrong</span>
              </div>
              <div className="flex items-center gap-2 text-blue-700">
                <Loader className="animate-spin" size={20} color="#3b82f6" />
                <span>Loading: Please wait...</span>
              </div>
            </div>
          </div>

          {/* Theme Toggle */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Theme Toggle:</p>
            <button className="flex items-center gap-2 px-4 py-2 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors">
              <Sun size={20} color="#f59e0b" />
              <span>Light Mode</span>
              <span className="mx-2">|</span>
              <Moon size={20} color="#6b7280" />
              <span>Dark Mode</span>
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="text-center text-gray-600 text-sm border-t pt-6">
        <p>
          Icon System v2.0 - Color & StrokeWidth Override Support
        </p>
        <p className="mt-2">
          Tüm icon'lar <a href="https://lucide.dev" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Lucide</a> kütüphanesinden
        </p>
      </footer>
    </div>
  );
}
