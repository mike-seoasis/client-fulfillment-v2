import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Tropical oasis palette - light, airy, lush greens
        // Primary accent: sage/palm green
        palm: {
          50: "#F6FAF7",
          100: "#E8F5EC",
          200: "#D1EADA",
          300: "#AEDABE",
          400: "#82C49D",
          500: "#5AAD7A",
          600: "#458C60",
          700: "#38704E",
          800: "#2F5A40",
          900: "#284A36",
        },
        // Background tones: warm sand/cream
        sand: {
          50: "#FDFCFA",
          100: "#FAF8F5",
          200: "#F5F1EB",
          300: "#EDE7DD",
          400: "#E2D9CB",
          500: "#D4C8B5",
          600: "#BBA992",
          700: "#9A8A72",
          800: "#736654",
          900: "#4D443A",
        },
        // Secondary accent: coral/terracotta (tropical flowers)
        coral: {
          50: "#FFF8F6",
          100: "#FFEFEB",
          200: "#FFDDD4",
          300: "#FFC7B8",
          400: "#FFAB96",
          500: "#F08B72",
          600: "#D4705A",
          700: "#B05746",
          800: "#854234",
          900: "#5A2C23",
        },
        // Deeper accent: lagoon teal
        lagoon: {
          50: "#F0FAFA",
          100: "#D6F3F3",
          200: "#AEE6E6",
          300: "#7AD3D5",
          400: "#4AB8BD",
          500: "#319A9F",
          600: "#297C82",
          700: "#266469",
          800: "#245256",
          900: "#224549",
        },
        // Neutral warm grays (unchanged - works well with greens)
        "warm-gray": {
          50: "#FAF9F7",
          100: "#F5F3F0",
          200: "#EAE6E1",
          300: "#DBD5CD",
          400: "#C4BBB0",
          500: "#A89E91",
          600: "#8A8076",
          700: "#6B635A",
          800: "#4D4842",
          900: "#302D29",
        },
        // Legacy alias for cream (points to sand now)
        cream: {
          50: "#FDFCFA",
          100: "#FAF8F5",
          200: "#F5F1EB",
          300: "#EDE7DD",
          400: "#E2D9CB",
          500: "#D4C8B5",
          600: "#BBA992",
          700: "#9A8A72",
          800: "#736654",
          900: "#4D443A",
        },
        // Legacy alias for gold (points to palm now)
        gold: {
          50: "#F6FAF7",
          100: "#E8F5EC",
          200: "#D1EADA",
          300: "#AEDABE",
          400: "#82C49D",
          500: "#5AAD7A",
          600: "#458C60",
          700: "#38704E",
          800: "#2F5A40",
          900: "#284A36",
        },
        // Semantic colors using warm palette
        background: "var(--background)",
        foreground: "var(--foreground)",
      },
      borderRadius: {
        // Sharp, refined corners - our design standard
        // Use rounded-sm (0.25rem) as default for most UI elements
        sm: "0.25rem",
        DEFAULT: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.625rem",
        "2xl": "0.75rem",
        "3xl": "1rem",
      },
    },
  },
  plugins: [],
};
export default config;
