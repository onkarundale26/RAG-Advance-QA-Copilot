/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#080b10",
        surface: "#111821",
        "surface-hover": "#172231",
        accent: "#2dd4bf",
        "accent-light": "#67e8f9",
        border: "#233041",
        success: "#34d399",
        text: {
          primary: "#f8fafc",
          secondary: "#b6c2d1",
          muted: "#718096"
        }
      }

    },
  },
  plugins: [],
}
