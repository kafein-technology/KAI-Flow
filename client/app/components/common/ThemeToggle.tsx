import { useThemeStore } from "~/stores/theme";
import { Sun, Moon } from "~/icons/index";

export function ThemeToggle() {
  const mode = useThemeStore((s) => s.mode);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);

  return (
    <button
      onClick={toggleTheme}
      className={`
          relative w-14 h-8 flex items-center rounded-full
          transition-colors duration-300
          ${mode === "dark" ? "bg-zinc-800" : "bg-yellow-200"}
          border border-gray-300 shadow-sm
          hover:scale-105 hover:shadow-md
        `}
      aria-label={`Switch to ${mode === "dark" ? "light" : "dark"} mode`}
    >
      {/* Track gradient */}
      <span
        className={`
            absolute inset-0 rounded-full pointer-events-none
            transition-all duration-500
            ${mode === "dark"
            ? "bg-gradient-to-r from-indigo-900/30 to-purple-900/30"
            : "bg-gradient-to-r from-yellow-100/60 to-yellow-300/60"
          }
          `}
      />
      {/* Toggle circle */}
      <span
        className={`
            z-10 w-7 h-7 rounded-full flex items-center justify-center
            transition-all duration-500
            ${mode === "dark"
            ? "bg-zinc-700 translate-x-6"
            : "bg-white translate-x-1"
          }
            shadow
          `}
      >
        {mode === "dark" ? (
          <Moon className="w-4 h-4 text-indigo-200" />
        ) : (
          <Sun className="w-4 h-4 text-yellow-500" />
        )}
      </span>
      {/* Static icons */}
      <span className="absolute left-2 z-0">
        <Sun
          className={`w-4 h-4 ${mode === "dark"
              ? "text-zinc-400 opacity-40"
              : "text-yellow-400 opacity-80"
            }`}
        />
      </span>
      <span className="absolute right-2 z-0">
        <Moon
          className={`w-4 h-4 ${mode === "dark"
              ? "text-indigo-300 opacity-80"
              : "text-zinc-400 opacity-40"
            }`}
        />
      </span>
    </button>
  );
}
