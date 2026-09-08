import baseConfig from "@kaihle/ui/tailwind.config.js";

export default {
  ...baseConfig,
  content: [
    "./src/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
    // getMasteryStyle/getConfidenceStyle return Tailwind class strings that exist ONLY
    // here. Without this glob those classes are never generated: the existing bg-/text-
    // ones survive only because the same literals happen to appear in app code, and
    // border-brand-*-dark appears nowhere else at all.
    "../../packages/types/src/**/*.{ts,tsx}",
  ],
};
