import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Warm palette for premium, approachable aesthetic
        gold: {
          50: "#FFFDF5",
          100: "#FFF9E6",
          200: "#FFF0C2",
          300: "#FFE499",
          400: "#FFD666",
          500: "#F5C242",
          600: "#D9A832",
          700: "#B8892A",
          800: "#8C6820",
          900: "#5C4515",
        },
        cream: {
          50: "#FFFEFB",
          100: "#FDFBF7",
          200: "#FAF6EE",
          300: "#F5EEE1",
          400: "#EDE3D0",
          500: "#E2D5BD",
          600: "#C9BCA3",
          700: "#A89A82",
          800: "#7D7260",
          900: "#524A3E",
        },
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
        // Semantic colors using warm palette
        background: "var(--background)",
        foreground: "var(--foreground)",
      },
      borderRadius: {
        // Slightly increased defaults for softer look
        sm: "0.25rem",
        DEFAULT: "0.375rem",
        md: "0.5rem",
        lg: "0.75rem",
        xl: "1rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
    },
  },
  plugins: [],
};
export default config;
