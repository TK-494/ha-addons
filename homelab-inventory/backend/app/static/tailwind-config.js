// Tailwind CDN runtime config. Has to live in an external file because the
// app's CSP doesn't allow inline scripts (which would otherwise be blocked
// silently — symptom is undefined custom colours like `bg-ha-500` and a
// dead `darkMode: 'media'` switch).
tailwind.config = {
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        // Sky scale, picked for WCAG-AA contrast with white text in both
        // light and dark mode (sky-700 light, sky-600 in dark).
        ha: {
          50:  '#f0f9ff',
          500: '#0284c7',
          600: '#0369a1',
          700: '#075985',
        },
      },
    },
  },
};
