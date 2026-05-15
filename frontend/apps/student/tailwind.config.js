import baseConfig from "@kaihle/ui/tailwind.config.js";

export default {
  ...baseConfig,
  content: ["./src/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    ...baseConfig.theme,
    extend: {
      ...baseConfig.theme?.extend,
      keyframes: {
        ...baseConfig.theme?.extend?.keyframes,
        "slide-in-right": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
      },
      animation: {
        ...baseConfig.theme?.extend?.animation,
        "slide-in-right": "slide-in-right 0.3s ease-out",
      },
    },
  },
};
