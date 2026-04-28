import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
    plugins: [react()],
    build: {
        outDir: path.resolve(__dirname, "../static/vite"),
        emptyOutDir: true,
        manifest: false,
        rollupOptions: {
            input: {
                login: path.resolve(__dirname, "src/login.jsx"),
                register: path.resolve(__dirname, "src/register.jsx"),
                core_app: path.resolve(__dirname, "src/core_app.jsx"),
            },
            output: {
                entryFileNames: "assets/[name].js",
                chunkFileNames: "assets/[name].js",
                assetFileNames: "assets/[name].[ext]",
            },
        },
    },
});

