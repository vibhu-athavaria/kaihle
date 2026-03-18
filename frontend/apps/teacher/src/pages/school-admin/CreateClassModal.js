import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from "react";
import { Button } from "@kaihle/ui";
import { Input } from "@kaihle/ui";
import { X } from "lucide-react";
import { useCurricula, useGrades, useSchoolUsers, useCreateClass, } from "../../hooks/useSchoolAdmin";
const subjectOptions = [
    { value: "MATH", label: "Mathematics" },
    { value: "SCI", label: "Science" },
    { value: "ENG", label: "English" },
    { value: "BIO", label: "Biology" },
    { value: "CHEM", label: "Chemistry" },
    { value: "PHY", label: "Physics" },
    { value: "ENGL", label: "English Literature" },
];
export function CreateClassModal({ isOpen, onClose, onCreated, }) {
    const [name, setName] = useState("");
    const [subject, setSubject] = useState("");
    const [grade, setGrade] = useState("");
    const [curriculumId, setCurriculumId] = useState("");
    const [teacherId, setTeacherId] = useState("");
    const [errors, setErrors] = useState({});
    const { data: curricula } = useCurricula();
    const { data: grades } = useGrades();
    const { data: teachers } = useSchoolUsers("TEACHER");
    const createClass = useCreateClass();
    useEffect(() => {
        if (grade && curricula && grades) {
            const gradeData = grades.find((g) => g.level === parseInt(grade));
            if (gradeData) {
                if (gradeData.level <= 8) {
                    const lowerCurriculum = curricula.find((c) => c.name.toLowerCase().includes("lower"));
                    if (lowerCurriculum) {
                        setCurriculumId(lowerCurriculum.id);
                    }
                }
                else if (gradeData.level <= 10) {
                    const igcseCurriculum = curricula.find((c) => c.name.toLowerCase().includes("igcse"));
                    if (igcseCurriculum) {
                        setCurriculumId(igcseCurriculum.id);
                    }
                }
            }
        }
    }, [grade, curricula, grades]);
    useEffect(() => {
        if (!isOpen) {
            setName("");
            setSubject("");
            setGrade("");
            setCurriculumId("");
            setTeacherId("");
            setErrors({});
        }
    }, [isOpen]);
    if (!isOpen)
        return null;
    const getSuggestedCurriculum = () => {
        if (!grade || !curricula)
            return "";
        const gradeNum = parseInt(grade);
        if (gradeNum <= 8) {
            return "Cambridge Lower Secondary";
        }
        if (gradeNum <= 10) {
            return "Cambridge IGCSE";
        }
        return "Cambridge A-Level";
    };
    const validate = () => {
        const newErrors = {};
        if (!name.trim()) {
            newErrors.name = "Class name is required";
        }
        if (!subject) {
            newErrors.subject = "Subject is required";
        }
        if (!grade) {
            newErrors.grade = "Grade is required";
        }
        if (!curriculumId) {
            newErrors.curriculum = "Curriculum is required";
        }
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validate())
            return;
        try {
            await createClass.mutateAsync({
                name: name.trim(),
                subject,
                grade: parseInt(grade),
                curriculum_id: curriculumId,
                teacher_id: teacherId || undefined,
            });
            onCreated();
            onClose();
        }
        catch {
            // Error handling done by caller
        }
    };
    return (_jsxs("div", { className: "fixed inset-0 z-50 flex items-center justify-center", children: [_jsx("div", { className: "absolute inset-0 bg-black/40", onClick: onClose, "aria-hidden": "true" }), _jsxs("div", { className: "relative bg-white rounded-2xl border border-brand-border shadow-xl p-6 w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-200", role: "dialog", "aria-modal": "true", "aria-labelledby": "modal-title", children: [_jsx("button", { onClick: onClose, className: "absolute top-4 right-4 p-1 text-brand-muted hover:text-brand-ink rounded-full hover:bg-gray-100", "aria-label": "Close", children: _jsx(X, { className: "w-5 h-5" }) }), _jsx("h2", { id: "modal-title", className: "text-xl font-display font-bold text-brand-ink mb-6", children: "Create a new class" }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsx("div", { children: _jsx(Input, { id: "className", label: "Class name", type: "text", value: name, onChange: (e) => setName(e.target.value), placeholder: "e.g. Maths 9B", error: errors.name }) }), _jsxs("div", { children: [_jsxs("label", { htmlFor: "subject", className: "block text-sm font-semibold text-brand-ink mb-1.5", children: ["Subject ", _jsx("span", { className: "text-brand-red", children: "*" })] }), _jsxs("select", { id: "subject", value: subject, onChange: (e) => setSubject(e.target.value), className: "w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary", children: [_jsx("option", { value: "", children: "Select subject" }), subjectOptions.map((opt) => (_jsx("option", { value: opt.value, children: opt.label }, opt.value)))] }), errors.subject && (_jsx("p", { className: "mt-1 text-xs text-brand-red", children: errors.subject }))] }), _jsxs("div", { children: [_jsxs("label", { htmlFor: "grade", className: "block text-sm font-semibold text-brand-ink mb-1.5", children: ["Grade ", _jsx("span", { className: "text-brand-red", children: "*" })] }), _jsxs("select", { id: "grade", value: grade, onChange: (e) => setGrade(e.target.value), className: "w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary", children: [_jsx("option", { value: "", children: "Select grade" }), grades?.map((g) => (_jsxs("option", { value: g.level, children: ["Grade ", g.level] }, g.id)))] }), errors.grade && (_jsx("p", { className: "mt-1 text-xs text-brand-red", children: errors.grade }))] }), _jsxs("div", { children: [_jsxs("label", { htmlFor: "curriculum", className: "block text-sm font-semibold text-brand-ink mb-1.5", children: ["Curriculum ", _jsx("span", { className: "text-brand-red", children: "*" })] }), _jsxs("select", { id: "curriculum", value: curriculumId, onChange: (e) => setCurriculumId(e.target.value), className: "w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary", children: [_jsx("option", { value: "", children: "Select curriculum" }), curricula?.map((c) => (_jsx("option", { value: c.id, children: c.name }, c.id)))] }), errors.curriculum && (_jsx("p", { className: "mt-1 text-xs text-brand-red", children: errors.curriculum })), grade && !errors.curriculum && (_jsxs("p", { className: "mt-1 text-xs text-brand-muted", children: ["Suggested: ", getSuggestedCurriculum()] }))] }), _jsxs("div", { children: [_jsx("label", { htmlFor: "teacher", className: "block text-sm font-semibold text-brand-ink mb-1.5", children: "Teacher (optional)" }), _jsxs("select", { id: "teacher", value: teacherId, onChange: (e) => setTeacherId(e.target.value), className: "w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary", children: [_jsx("option", { value: "", children: "Select teacher" }), teachers?.map((t) => (_jsxs("option", { value: t.id, children: [t.first_name, " ", t.last_name] }, t.id)))] })] }), _jsxs("div", { className: "flex gap-3 pt-4", children: [_jsx(Button, { type: "button", variant: "secondary", onClick: onClose, className: "flex-1", children: "Cancel" }), _jsx(Button, { type: "submit", variant: "primary", loading: createClass.isPending, className: "flex-1", children: "Create class \u2192" })] })] })] })] }));
}
