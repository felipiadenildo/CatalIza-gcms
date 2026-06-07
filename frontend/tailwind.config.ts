import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas:    "#0d1117",
        surface1:  "#161b22",
        surface2:  "#21262d",
        border:    "#30363d",
        text:      "#e6edf3",
        muted:     "#8b949e",
        accent:    "#58a6ff",
        success:   "#3fb950",
        warning:   "#d29922",
        danger:    "#f85149",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;