import { createContext, useCallback, useContext } from "react";
import type { Messages } from "@/i18n/es";

export type Language = "es" | "en";
export type ThemePreference = "light" | "dark" | "system";
export type MotionPreference = "system" | "reduce" | "full";

export interface Preferences {
  language: Language;
  theme: ThemePreference;
  motion: MotionPreference;
  /** Resolved values */
  resolvedTheme: "light" | "dark";
  reducedMotion: boolean;
  messages: Messages;
  setLanguage: (language: Language) => void;
  setTheme: (theme: ThemePreference) => void;
  setMotion: (motion: MotionPreference) => void;
}

export const PreferencesContext = createContext<Preferences | null>(null);

export function usePreferences(): Preferences {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error("usePreferences must be used inside PreferencesProvider");
  return ctx;
}

/** Translation messages for the current language, plus locale-aware formatters. */
export function useI18n() {
  const { messages, language } = usePreferences();
  const locale = language === "es" ? "es-ES" : "en-GB";
  const number = useCallback(
    (value: number, options?: Intl.NumberFormatOptions) => new Intl.NumberFormat(locale, options).format(value),
    [locale],
  );
  const percent = useCallback(
    (value: number, digits = 1) =>
      new Intl.NumberFormat(locale, { style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value),
    [locale],
  );
  const dateTime = useCallback(
    (value: string | Date) =>
      new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)),
    [locale],
  );
  return { t: messages, language, locale, number, percent, dateTime };
}
