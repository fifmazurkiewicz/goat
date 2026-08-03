module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  ignorePatterns: ["dist", ".eslintrc.cjs"],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["react-refresh"],
  rules: {
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
  },
  overrides: [
    {
      // Konwencja shadcn/ui: pliki komponentów eksportują obok komponentu też
      // powiązane `cva()` warianty/stałe (np. `buttonVariants`) — akceptowany
      // wzorzec biblioteki, niewart refaktoru na osobne pliki per eksport.
      files: ["src/components/ui/**/*.tsx"],
      rules: { "react-refresh/only-export-components": "off" },
    },
  ],
};
