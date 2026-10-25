import { useEffect, useState } from "react";
import { api } from "./api.js";

/**
 * "I updated the add-on and nothing changed."
 *
 * A browser that cached `index.html` keeps running an old bundle while the
 * add-on reports a new version, and nothing on screen admits it — three
 * releases went by unseen that way, and the only clue was a missing button.
 *
 * So the page checks whether the script it was loaded from is still the one
 * the server points at, and says so when it is not. Reloading goes to a URL
 * the browser has never seen, because a plain reload would be served from the
 * same cache that caused the problem.
 */
const OWN_BUNDLE = (() => {
  try {
    return import.meta.url.split("/").pop();
  } catch {
    return null;
  }
})();

export default function StaleBuild() {
  const [stale, setStale] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const check = () => api.health()
      .then(({ bundle, version }) => {
        if (cancelled || !bundle || !OWN_BUNDLE) return;
        if (bundle.split("/").pop() !== OWN_BUNDLE) setStale(version);
      })
      .catch(() => { /* offline or restarting; the next tick tries again */ });

    check();
    // An add-on restart mid-session should surface within a few minutes.
    const timer = setInterval(check, 5 * 60 * 1000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  if (!stale) return null;

  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-amber-100 px-4 py-3 text-sm text-amber-900 dark:bg-amber-900 dark:text-amber-50">
      <span>
        Je bekijkt een oudere versie van deze pagina uit het geheugen van je browser.
        Versie <strong>{stale}</strong> staat klaar.
      </span>
      <button
        className="btn-primary"
        onClick={() => {
          const url = new URL(window.location.href);
          url.searchParams.set("v", Date.now().toString());
          window.location.replace(url.toString());
        }}
      >
        Nieuwe versie laden
      </button>
    </div>
  );
}
