import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // 전문 금융 플랫폼 톤: 절제된 네이비/그레이 팔레트 (요구사항 60: 과도한 gradient/neon 금지)
        brand: {
          DEFAULT: "#0f2942",
          light: "#1e4266",
        },
        positive: "#c0392b", // 국내 관행: 상승=적색
        negative: "#2563eb", // 하락=청색
        surface: "#f7f8fa",
      },
    },
  },
  plugins: [],
};

export default config;
