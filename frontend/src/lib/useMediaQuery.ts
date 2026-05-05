import { useEffect, useState } from "react";

/** Returns true while the given media query matches. SSR-safe (returns false
 * during the first render on environments without window). */
export function useMediaQuery(query: string): boolean {
  const get = () =>
    typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia(query).matches
      : false;
  const [matches, setMatches] = useState(get);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(query);
    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener("change", listener);
    setMatches(mql.matches);
    return () => mql.removeEventListener("change", listener);
  }, [query]);

  return matches;
}
