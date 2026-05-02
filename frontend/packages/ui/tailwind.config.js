/** @type {import('tailwindcss').Config} */
// ============================================================
// Kaihle Shared Tailwind Configuration v2.0
// Location: frontend/packages/ui/tailwind.config.js
//
// USAGE in each app's tailwind.config.js:
//
//   import baseConfig from '@kaihle/ui/tailwind.config.js'
//   export default {
//     ...baseConfig,
//     content: ['./src/**/*.{ts,tsx}', '../../packages/ui/src/**/*.{ts,tsx}'],
//   }
//
// All five roles use this file. Role-specific tokens are prefixed role-*.
// See docs/design/DESIGN_SYSTEM.md for full usage guidance.
// ============================================================

export default {
  content: ["./src/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // ── COMPACT UI TOKENS ───────────────────────────────────
      // All values match docs/design/mockups/student_dashboard.html exactly.
      // Use these token names in components — never use text-[Npx] in JSX.
      fontSize: {
        // Sidebar chrome
        "sidebar-logo": ["15px", { lineHeight: "1" }],
        "sidebar-label": ["9px", { lineHeight: "1" }],
        "sidebar-nav": ["12px", { lineHeight: "1.25" }],
        "sidebar-profile": ["11px", { lineHeight: "1.2" }],
        "sidebar-grade": ["9px", { lineHeight: "1" }],
        "sidebar-avatar": ["10px", { lineHeight: "1" }],
        // Top nav
        "topnav-greeting": ["13px", { lineHeight: "1.25" }],
        "topnav-sub": ["10px", { lineHeight: "1" }],
        // Page section labels
        "section-label": ["9px", { lineHeight: "1" }],
        // Score cards
        "score-value": ["20px", { lineHeight: "1" }],
        "score-subject": ["9px", { lineHeight: "1" }],
        "score-band": ["9px", { lineHeight: "1" }],
        // Class cards
        "card-title": ["11px", { lineHeight: "1.3" }],
        "card-meta": ["9px", { lineHeight: "1.4" }],
        "card-action": ["10px", { lineHeight: "1" }],
        // Next step cards
        "step-title": ["11px", { lineHeight: "1.3" }],
        "step-sub": ["9px", { lineHeight: "1.4" }],
        "step-action": ["10px", { lineHeight: "1" }],
      },
      // ── FONT FAMILIES ──────────────────────────────────────
      fontFamily: {
        // Nunito: base body font — ALL roles
        sans: ["Nunito", "ui-sans-serif", "system-ui", "sans-serif"],
        // Fraunces: display headings — School Admin, Teacher, Student
        display: ["Fraunces", "Georgia", "ui-serif", "serif"],
        // Inter: Kaihle Admin only (monospace fallback for dense data)
        // Lora: Parent only — both configured via font-['Lora'] in JSX
        // All four fonts loaded via Google Fonts in each app's index.css
      },

      // ── SHARED BRAND TOKENS ────────────────────────────────
      // Used across all five roles. Source: docs/design/DESIGN_SYSTEM.md §2
      colors: {
        brand: {
          // Forest Green — primary brand + mastery Strong
          primary: "#1a5c38",
          dark: "#0f3d25", // hover on primary
          light: "#e8f2ea", // green tint
          mid: "#b5d4bc", // green borders

          // Mastery Strong — use these for Strong dots/bars (NOT emerald-*)
          green: "#16a34a",
          "green-light": "#dcfce7",

          // Mastery Developing
          amber: "#f59e0b",
          "amber-light": "#fef3c7",

          // Mastery Needs Work
          red: "#ef4444",
          "red-light": "#fee2e2",

          // Gold — accent, Teacher primary action, developing states
          gold: "#c9932a",
          "gold-light": "#f5ead0",
          "gold-mid": "#e8c97a",
          "gold-dark": "#92400e", // text on gold tint backgrounds

          // Text
          ink: "#1a2016", // primary text (Teacher, Student, School Admin)
          body: "#4a5240", // secondary body text
          muted: "#9ca3af", // placeholder, disabled

          // Surfaces
          bg: "#f5f7f1", // page background (Teacher, School Admin)
          "surface-subtle": "#fafcfa", // table header tint, footer stripe
          "green-pale": "#f0fdf4", // very light green tint (badges, highlights)

          // Borders
          border: "#e5e7eb", // default border (Teacher, Student)
          "border-soft": "#f3f4f6", // subtle separator
          "row-divider": "#f0f5ee", // table row separator (green-tinted)
        },

        // ── KAIHLE ADMIN TOKENS ──────────────────────────────
        // Surgical Slate — Inter font, blue-gray system feel
        // CONSTITUTION: internal ops tool for Vibhu and team
        "role-admin": {
          bg: "#f8f9fb", // page background — cool blue-gray
          sidebar: "#ffffff", // sidebar
          border: "#eaecf0", // all borders
          mark: "#374151", // logo mark background (gray-700)
          ink: "#111827", // primary text (gray-900)
          muted: "#9ca3af", // section labels, secondary
          subtle: "#6b7280", // inactive nav items (gray-500)
        },

        // ── SCHOOL ADMIN TOKENS ──────────────────────────────
        // Sage Authority — green-tinted borders, left stripe active
        // CONSTITUTION: strategic oversight, billing, analytics
        "role-school": {
          bg: "#f5f7f1", // page background — same as Teacher (brand cream)
          sidebar: "#ffffff", // sidebar
          border: "#d4e4d8", // borders — green-tinted sand
          muted: "#6b9e79", // section labels — muted green
          subtle: "#4a5240", // inactive nav (same as brand-body)
        },

        // ── TEACHER TOKENS ───────────────────────────────────
        // Focused Workspace — gold actions, green data only
        // CONSTITUTION: classroom teacher, gap map, lesson plans
        "role-teacher": {
          bg: "#f5f7f1", // page background
          sidebar: "#ffffff", // sidebar
          border: "#e5e7eb", // borders — neutral gray (same as brand-border)
          muted: "#9ca3af", // section labels (same as brand-muted)
          body: "#4a5240", // secondary text, inactive nav
          "nav-active": "#fffbeb",
        },

        // ── STUDENT TOKENS ───────────────────────────────────
        // Airy & Encouraging — mobile-first, colored-border cards
        // CONSTITUTION: ages 11-18, phone-primary, daily use
        "role-student": {
          bg: "#f9fafb", // page background
          border: "#e5e7eb", // card borders, dividers
          "nav-active": "#f0fdf4", // active sidebar nav tint (NOT the mastery Strong tint)
          "nav-locked-hover": "#fffbeb", // hover tint for locked class items (amber/gold tint)
        },

        // ── PARENT TOKENS ────────────────────────────────────
        // Warm & Readable — Lora editorial, narrow reading column
        // CONSTITUTION: non-technical, phone-first, 90-second weekly check-in
        "role-parent": {
          bg: "#fdf8f0", // page background — warm cream
          card: "#ffffff", // card surfaces
          border: "#e8dcc8", // borders — warm sand
          ink: "#2c1a0e", // primary text — espresso (warmer than brand-ink)
          muted: "#a08060", // secondary text — warm taupe
          // Narrative: font-['Lora'] text-sm leading-relaxed text-role-parent-ink
        },
      },

      // ── BORDER RADIUS ──────────────────────────────────────
      borderRadius: {
        "2xl": "1rem", // modals, large cards
        "3xl": "1.5rem", // large panels
        nav: "6px", // sidebar nav item radius
        card: "10px", // dashboard compact cards (score, class, next step)
      },

      // ── BOX SHADOWS ────────────────────────────────────────
      boxShadow: {
        card: "0 2px 12px rgba(30,27,75,0.04)",
        "card-hover": "0 8px 30px rgba(26,92,56,0.08)",
        btn: "0 4px 14px rgba(26,92,56,0.20)",
      },
    },
  },
  plugins: [],
};
