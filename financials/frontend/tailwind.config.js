/**
 * Colour scales resolve through CSS variables so a theme can be swapped at
 * runtime.
 *
 * The alternative was rewriting 360 colour classes across 20 files every time
 * a palette changes. Tailwind's `<alpha-value>` placeholder keeps opacity
 * modifiers (`bg-slate-500/40`) working, which a plain `var()` would break.
 */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        slate: {
          50: "rgb(var(--c-slate-50) / <alpha-value>)",
          100: "rgb(var(--c-slate-100) / <alpha-value>)",
          200: "rgb(var(--c-slate-200) / <alpha-value>)",
          300: "rgb(var(--c-slate-300) / <alpha-value>)",
          400: "rgb(var(--c-slate-400) / <alpha-value>)",
          500: "rgb(var(--c-slate-500) / <alpha-value>)",
          600: "rgb(var(--c-slate-600) / <alpha-value>)",
          700: "rgb(var(--c-slate-700) / <alpha-value>)",
          800: "rgb(var(--c-slate-800) / <alpha-value>)",
          900: "rgb(var(--c-slate-900) / <alpha-value>)",
          950: "rgb(var(--c-slate-950) / <alpha-value>)",
        },
        sky: {
          50: "rgb(var(--c-sky-50) / <alpha-value>)",
          100: "rgb(var(--c-sky-100) / <alpha-value>)",
          200: "rgb(var(--c-sky-200) / <alpha-value>)",
          300: "rgb(var(--c-sky-300) / <alpha-value>)",
          400: "rgb(var(--c-sky-400) / <alpha-value>)",
          500: "rgb(var(--c-sky-500) / <alpha-value>)",
          600: "rgb(var(--c-sky-600) / <alpha-value>)",
          700: "rgb(var(--c-sky-700) / <alpha-value>)",
          800: "rgb(var(--c-sky-800) / <alpha-value>)",
          900: "rgb(var(--c-sky-900) / <alpha-value>)",
          950: "rgb(var(--c-sky-950) / <alpha-value>)",
        },
        emerald: {
          50: "rgb(var(--c-emerald-50) / <alpha-value>)",
          100: "rgb(var(--c-emerald-100) / <alpha-value>)",
          200: "rgb(var(--c-emerald-200) / <alpha-value>)",
          300: "rgb(var(--c-emerald-300) / <alpha-value>)",
          400: "rgb(var(--c-emerald-400) / <alpha-value>)",
          500: "rgb(var(--c-emerald-500) / <alpha-value>)",
          600: "rgb(var(--c-emerald-600) / <alpha-value>)",
          700: "rgb(var(--c-emerald-700) / <alpha-value>)",
          800: "rgb(var(--c-emerald-800) / <alpha-value>)",
          900: "rgb(var(--c-emerald-900) / <alpha-value>)",
          950: "rgb(var(--c-emerald-950) / <alpha-value>)",
        },
        rose: {
          50: "rgb(var(--c-rose-50) / <alpha-value>)",
          100: "rgb(var(--c-rose-100) / <alpha-value>)",
          200: "rgb(var(--c-rose-200) / <alpha-value>)",
          300: "rgb(var(--c-rose-300) / <alpha-value>)",
          400: "rgb(var(--c-rose-400) / <alpha-value>)",
          500: "rgb(var(--c-rose-500) / <alpha-value>)",
          600: "rgb(var(--c-rose-600) / <alpha-value>)",
          700: "rgb(var(--c-rose-700) / <alpha-value>)",
          800: "rgb(var(--c-rose-800) / <alpha-value>)",
          900: "rgb(var(--c-rose-900) / <alpha-value>)",
          950: "rgb(var(--c-rose-950) / <alpha-value>)",
        },
        amber: {
          50: "rgb(var(--c-amber-50) / <alpha-value>)",
          100: "rgb(var(--c-amber-100) / <alpha-value>)",
          200: "rgb(var(--c-amber-200) / <alpha-value>)",
          300: "rgb(var(--c-amber-300) / <alpha-value>)",
          400: "rgb(var(--c-amber-400) / <alpha-value>)",
          500: "rgb(var(--c-amber-500) / <alpha-value>)",
          600: "rgb(var(--c-amber-600) / <alpha-value>)",
          700: "rgb(var(--c-amber-700) / <alpha-value>)",
          800: "rgb(var(--c-amber-800) / <alpha-value>)",
          900: "rgb(var(--c-amber-900) / <alpha-value>)",
          950: "rgb(var(--c-amber-950) / <alpha-value>)",
        },
        indigo: {
          50: "rgb(var(--c-indigo-50) / <alpha-value>)",
          100: "rgb(var(--c-indigo-100) / <alpha-value>)",
          200: "rgb(var(--c-indigo-200) / <alpha-value>)",
          300: "rgb(var(--c-indigo-300) / <alpha-value>)",
          400: "rgb(var(--c-indigo-400) / <alpha-value>)",
          500: "rgb(var(--c-indigo-500) / <alpha-value>)",
          600: "rgb(var(--c-indigo-600) / <alpha-value>)",
          700: "rgb(var(--c-indigo-700) / <alpha-value>)",
          800: "rgb(var(--c-indigo-800) / <alpha-value>)",
          900: "rgb(var(--c-indigo-900) / <alpha-value>)",
          950: "rgb(var(--c-indigo-950) / <alpha-value>)",
        },
      },
    },
  },
  plugins: [],
};
