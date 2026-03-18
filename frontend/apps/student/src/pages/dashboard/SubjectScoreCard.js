import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";
const borderClassMap = {
    "bg-brand-green-light": "border-brand-mid",
    "bg-brand-amber-light": "border-brand-gold-mid",
    "bg-brand-red-light": "border-brand-red/30",
    "bg-gray-50": "border-brand-border",
};
export function SubjectScoreCard({ subjectName, subjectCode: _subjectCode, score, }) {
    const { bgClass, textClass, label } = getMasteryStyle(score);
    const borderClass = borderClassMap[bgClass] ?? "border-brand-border";
    const displayPct = scoreToPercent(score);
    return (_jsxs("div", { className: `bg-white rounded-2xl border-[1.5px] ${borderClass} p-4 text-center`, children: [_jsx("div", { className: `text-2xl font-extrabold ${textClass}`, children: displayPct }), _jsx("div", { className: "text-xs font-bold uppercase tracking-wide text-brand-muted mt-1", children: subjectName }), _jsx("div", { className: "text-xs text-brand-muted mt-0.5", children: label })] }));
}
