/** Themes are one attribute on <html>; the CSS variables do the rest. */
export function applyTheme(theme) {
  if (!theme || theme === "default") {
    delete document.documentElement.dataset.theme;
  } else {
    document.documentElement.dataset.theme = theme;
  }
}

export const THEMES = [
  {
    value: "default",
    label: "Standaard",
    description: "Neutrale grijstinten met blauw accent.",
    swatches: ["#0ea5e9", "#64748b", "#10b981", "#f43f5e"],
  },
  {
    value: "google",
    label: "Google",
    description:
      "Google Material: dezelfde blauw, rood, geel en groen als het Google-thema in Home Assistant, " +
      "met vlakke kaarten en ronde knoppen.",
    swatches: ["#1a73e8", "#5f6368", "#34a853", "#ea4335"],
  },
];
