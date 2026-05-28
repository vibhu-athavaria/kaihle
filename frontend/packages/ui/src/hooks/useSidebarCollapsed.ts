import { useState, useCallback } from "react";

const STORAGE_KEY = "kaihle_sidebar_collapsed";

export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // ignore — localStorage unavailable in some envs
      }
      return next;
    });
  }, []);

  return { collapsed, toggle };
}
