export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        hull: "#0b1117",
        panel: "#121a22",
        line: "#24313d",
        cyan: "#6ee7f9",
        mint: "#79f2b0",
        amber: "#f6c760",
        danger: "#ff6b6b",
      },
    },
  },
  plugins: [],
};
