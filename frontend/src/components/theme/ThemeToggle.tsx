import { Moon, Sun } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useTheme } from "./ThemeProvider";

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      aria-pressed={isDark}
      className={`relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-rule bg-surface text-ink-soft transition-colors hover:text-ink hover:bg-surface-muted ${className ?? ""}`}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={isDark ? "moon" : "sun"}
          initial={{ opacity: 0, rotate: -45, scale: 0.85 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          exit={{ opacity: 0, rotate: 45, scale: 0.85 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          className="flex"
        >
          {isDark ? <Moon size={16} strokeWidth={1.6} /> : <Sun size={16} strokeWidth={1.6} />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
