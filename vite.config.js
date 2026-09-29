import { defineConfig } from "vite";

export default defineConfig({
  root: "src",
  base: "./",
  build: {
    outDir: "../dist-web",
    emptyOutDir: true,
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    include: ["../tests-js/**/*.test.js"],
  },
});
