/**
 * ScoreRing — Teacher app copy.
 * SVG progress ring for mastery score display on assessment results pages.
 *
 * Teacher-specific sizing: uses a 100×100 viewBox per spec.
 * Animation respects prefers-reduced-motion via motion-safe: Tailwind prefix.
 * Accessibility: role="img", aria-label, <title> inside SVG.
 */
import React from "react";
import { getMasteryStyle } from "@kaihle/types";

interface ScoreRingProps {
  /** Score as float 0.0–1.0 or null for "not assessed" */
  score: number | null;
  /** Additional CSS classes for the SVG element */
  className?: string;
}

const RADIUS = 42;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS; // ≈ 263.9

export function ScoreRing({
  score,
  className = "",
}: ScoreRingProps): React.JSX.Element {
  const style = getMasteryStyle(score);
  const offset = score === null ? CIRCUMFERENCE : CIRCUMFERENCE * (1 - score);
  const displayPct = score === null ? "—" : `${Math.round(score * 100)}%`;
  const ariaLabel =
    score === null
      ? "Not assessed"
      : `${Math.round(score * 100)}% — ${style.label}`;

  return (
    <svg
      width={100}
      height={100}
      viewBox="0 0 100 100"
      role="img"
      aria-label={ariaLabel}
      className={className}
    >
      <title>{ariaLabel}</title>
      {/* Background track */}
      <circle
        cx={50}
        cy={50}
        r={RADIUS}
        fill="none"
        stroke="#e5e7eb"
        strokeWidth={10}
      />
      {/* Progress arc */}
      <circle
        cx={50}
        cy={50}
        r={RADIUS}
        fill="none"
        stroke={style.strokeColour}
        strokeWidth={10}
        strokeLinecap="round"
        strokeDasharray={CIRCUMFERENCE}
        strokeDashoffset={offset}
        transform="rotate(-90 50 50)"
        className="motion-safe:transition-[stroke-dashoffset] motion-safe:duration-[600ms] motion-safe:ease-out"
      />
      {/* Score percentage — Fraunces bold */}
      <text
        x={50}
        y={46}
        textAnchor="middle"
        dominantBaseline="central"
        fill={style.fillColour}
        fontFamily="Fraunces, Georgia, serif"
        fontWeight="700"
        fontSize="22"
      >
        {displayPct}
      </text>
      {/* Band label — Nunito */}
      <text
        x={50}
        y={64}
        textAnchor="middle"
        dominantBaseline="central"
        fill="#9ca3af"
        fontFamily="Nunito, sans-serif"
        fontSize="10"
      >
        {style.label}
      </text>
    </svg>
  );
}
