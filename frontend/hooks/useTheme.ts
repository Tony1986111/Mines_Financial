"use client";

import { useCallback, useEffect, useState } from "react";

export function useTheme() {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme") ?? "light";
    const nextIsDark = saved === "dark";
    setIsDark(nextIsDark);
    document.documentElement.classList.toggle("dark", nextIsDark);
  }, []);

  const toggleTheme = useCallback(() => {
    setIsDark(current => {
      const nextIsDark = !current;
      localStorage.setItem("theme", nextIsDark ? "dark" : "light");
      document.documentElement.classList.toggle("dark", nextIsDark);
      return nextIsDark;
    });
  }, []);

  return { isDark, toggleTheme };
}
