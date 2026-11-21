import { defineConfig } from "vitest/config";

export default defineConfig({
  // mesmo atalho `@/` do tsconfig ("/src" é a raiz do projeto para o Vite), para testar módulos que importam por ele
  resolve: { alias: { "@": "/src" } },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
