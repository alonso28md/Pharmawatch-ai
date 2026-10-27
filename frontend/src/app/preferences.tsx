import { MotionConfig } from "motion/react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { en } from "@/i18n/en";
import { es, type Messages } from "@/i18n/es";
import {
  type Language,
  type MotionPreference,
  type Preferences,
  PreferencesContext,
  type ThemePreference,
} from "./preferencesContext";

const DICTIONARIES: Record<Language, Messages> = { es, en };
const STORAGE_KEY = "pharmawatch.preferences"; // non-sensitive UI preferences only

function readStored(): Partial<Pick<Preferences, "language" | "theme" | "motion">> {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function detectLanguage(): Language {
  const langs = typeof navigator !== "undefined" ? navigator.languages ?? [navigator.language] : [];
  return langs.some((l) => l?.toLowerCase().startsWith("es")) ? "es" : "en";
}

function useMediaQuery(query: string): boolean {
  const get = () => typeof window !== "undefined" && window.matchMedia?.(query).matches === true;
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    const mql = window.matchMedia?.(query);
    if (!mql) return;
    const onChange = () => setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [stored] = useState(readStored);
  const [language, setLanguage] = useState<Language>(stored.language ?? detectLanguage());
  const [theme, setTheme] = useState<ThemePreference>(stored.theme ?? "system");
  const [motion, setMotion] = useState<MotionPreference>(stored.motion ?? "system");
  const prefersDark = useMediaQuery("(prefers-color-scheme: dark)");
  const prefersReduced = useMediaQuery("(prefers-reduced-motion: reduce)");

  const resolvedTheme = theme === "system" ? (prefersDark ? "dark" : "light") : theme;
  const reducedMotion = motion === "system" ? prefersReduced : motion === "reduce";

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = resolvedTheme;
    root.dataset.reducedMotion = String(reducedMotion);
    root.lang = language;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", resolvedTheme === "dark" ? "#111315" : "#f6f5f2");
  }, [resolvedTheme, reducedMotion, language]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ language, theme, motion }));
    } catch {
      /* storage unavailable */
    }
  }, [language, theme, motion]);

  const value = useMemo<Preferences>(
    () => ({
      language, theme, motion, resolvedTheme, reducedMotion,
      messages: DICTIONARIES[language],
      setLanguage, setTheme, setMotion,
    }),
    [language, theme, motion, resolvedTheme, reducedMotion],
  );

  return (
    <PreferencesContext.Provider value={value}>
      <MotionConfig reducedMotion={reducedMotion ? "always" : "never"}>{children}</MotionConfig>
    </PreferencesContext.Provider>
  );
}
