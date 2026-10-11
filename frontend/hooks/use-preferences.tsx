"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
type Language = "zh" | "en";
interface Preferences {
  language: Language;
  theme: "dark" | "light";
  saved: string[];
  t: (zh: string, en: string) => string;
  toggleTheme: () => void;
  toggleLanguage: () => void;
  toggleSaved: (id: string) => void;
}
const Context = createContext<Preferences | null>(null);
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [language, setLanguage] = useState<Language>("zh");
  const [saved, setSaved] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try {
      setTheme(localStorage.getItem("mi-theme") === "light" ? "light" : "dark");
      setLanguage(localStorage.getItem("mi-language") === "en" ? "en" : "zh");
      const ids = JSON.parse(localStorage.getItem("mi-saved") || "[]");
      if (Array.isArray(ids))
        setSaved(
          ids.filter((id: unknown) => typeof id === "string").slice(0, 500),
        );
    } catch {
      /* Storage is optional in private browsing. */
    }
    setReady(true);
  }, []);
  useEffect(() => {
    if (ready && document.documentElement.dataset.theme !== theme)
      document.documentElement.dataset.theme = theme;
  }, [theme, ready]);
  useEffect(() => {
    const locale = language === "zh" ? "zh-CN" : "en";
    if (ready && document.documentElement.lang !== locale)
      document.documentElement.lang = locale;
  }, [language, ready]);
  function persist(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* Keep the in-memory preference. */
    }
  }
  return (
    <Context.Provider
      value={{
        theme,
        language,
        saved,
        t: (zh, en) => (language === "zh" ? zh : en),
        toggleTheme: () => {
          const next = theme === "dark" ? "light" : "dark";
          setTheme(next);
          persist("mi-theme", next);
        },
        toggleLanguage: () => {
          const next = language === "zh" ? "en" : "zh";
          setLanguage(next);
          persist("mi-language", next);
        },
        toggleSaved: (id) =>
          setSaved((previous) => {
            const next = previous.includes(id)
              ? previous.filter((item) => item !== id)
              : [...previous, id].slice(-500);
            persist("mi-saved", JSON.stringify(next));
            return next;
          }),
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function usePreferences() {
  const value = useContext(Context);
  if (!value) throw new Error("PreferencesProvider missing");
  return value;
}
