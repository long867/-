import type { Config } from "tailwindcss";
export default {
  darkMode: ["class", "[data-theme=dark]"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "var(--accent)",
        ink: "var(--text)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        surface: "var(--surface)",
        border: "var(--border)",
      },
    },
  },
  plugins: [],
} satisfies Config;
