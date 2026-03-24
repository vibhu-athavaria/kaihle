/**
 * ScoreRing - SVG progress ring for mastery scores.
 * Used across Teacher app, Student app for assessment results and profiles.
 */
import React from "react";
import { getMasteryStyle } from "@kaihle/types";

type ScoreRingSize = "sm" | "md" | "lg";

interface ScoreRingProps {
  /** Score as float 0.0–1.0 or null for "not assessed" */
  score: number | null;
  /** Size variant, default 'md' */
  size?: ScoreRingSize;
  /** Additional CSS classes */
  className?: string;
}

const sizeConfig: Record<
  ScoreRingSize,
  { diameter: number; radius: number; strokeWidth: number; fontSize: string }
> = {
  sm: { diameter: 48, radius: 20, strokeWidth: 4, fontSize: "0.75rem" },
  md: { diameter: 80, radius: 36, strokeWidth: 7, fontSize: "0.875rem" },
  lg: { diameter: 100, radius: 45, strokeWidth: 10, fontSize: "1.125rem" },
};

export function ScoreRing({
  score,
  size = "md",
  className = "",
}: ScoreRingProps): React.JSX.Element {
  const { diameter, radius, strokeWidth, fontSize } = sizeConfig[size];
  const cx = diameter / 2;
  const cy = diameter / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = score === null ? 0 : circumference * (1 - score);

  const style = getMasteryStyle(score);
  const displayText = score === null ? "—" : `${Math.round(score * 100)}%`;
  const ariaLabel =
    score === null
      ? "Not assessed"
      : `${Math.round(score * 100)}% — ${style.label}`;

  return (
    <svg
      width={diameter}
      height={diameter}
      viewBox={`0 0 ${diameter} ${diameter}`}
      role="img"
      aria-label={ariaLabel}
      className={className}
    >
      {/* Background arc */}
      <circle
        cx={cx}
        cy={cy}
        r={radius}
        fill="none"
        stroke="#e5e7eb"
        strokeWidth={strokeWidth}
      />
      {/* Progress arc */}
      <circle
        cx={cx}
        cy={cy}
        r={radius}
        fill="none"
        stroke={style.strokeColour}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${cx} ${cy})`}
        className="motion-safe:transition-all motion-safe:duration-600 motion-safe:ease-out"
      />
      {/* Center text */}
      <text
        x={cx}
        y={cy}
        textAnchor="middle"
        dominantBaseline="central"
        fill={style.fillColour}
        fontWeight="700"
        fontSize={fontSize}
      >
        {displayText}
      </text>
    </svg>
  );
}
