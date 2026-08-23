/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Exactly one accent color, per the spec -- used sparingly, only
        // for emphasis and the active tab.
        accent: {
          DEFAULT: "#4A90D9",
          50: "#EEF5FC",
          100: "#DCEAFA",
          400: "#6BA6E3",
          500: "#4A90D9",
          600: "#3A78BE",
        },
        bull: "#1D8348",
        bear: "#C0392B",
        ink: {
          900: "#14181F",
          700: "#3A4150",
          500: "#6B7280",
          300: "#B4B9C2",
          100: "#E7E9EC",
        },
        surface: "#FFFFFF",
        canvas: "#F6F8FB",
      },
      fontFamily: {
        sans: ["'Inter'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "'SF Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(20, 24, 31, 0.04), 0 4px 16px rgba(20, 24, 31, 0.06)",
      },
      borderRadius: {
        card: "18px",
      },
    },
  },
  plugins: [],
};
