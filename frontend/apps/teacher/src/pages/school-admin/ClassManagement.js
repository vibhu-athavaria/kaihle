import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from "react";
import { DashboardLayout } from "@kaihle/ui";
import { Card } from "@kaihle/ui";
import { Badge } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import { Plus, X, BookOpen } from "lucide-react";
import { useSchoolClasses, useSchoolUsers, useUpdateClass, useEnrollStudents, } from "../../hooks/useSchoolAdmin";
import { CreateClassModal } from "./CreateClassModal";
function ClassDetailPanel({ cls, teachers, students, onClose, onUpdateTeacher, onEnrollStudents, onDeactivate, }) {
    const [selectedTeacherId, setSelectedTeacherId] = useState(cls.teacher_id || "");
    const [isEnrollOpen, setIsEnrollOpen] = useState(false);
    const [selectedStudents, setSelectedStudents] = useState([]);
    const handleTeacherChange = () => {
        if (selectedTeacherId !== cls.teacher_id) {
            onUpdateTeacher(selectedTeacherId);
        }
    };
    const toggleStudent = (studentId) => {
        setSelectedStudents((prev) => prev.includes(studentId)
            ? prev.filter((id) => id !== studentId)
            : [...prev, studentId]);
    };
    const handleEnroll = () => {
        if (selectedStudents.length > 0) {
            onEnrollStudents(selectedStudents);
            setIsEnrollOpen(false);
            setSelectedStudents([]);
        }
    };
    const enrolledStudents = students.slice(0, 10);
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "fixed inset-0 bg-black/20 z-40", onClick: onClose }), _jsx("div", { className: "fixed right-0 top-0 h-full w-80 bg-white border-l border-brand-border shadow-xl z-50 overflow-y-auto animate-in slide-in-from-right duration-200", children: _jsxs("div", { className: "p-6", children: [_jsxs("div", { className: "flex items-center justify-between mb-6", children: [_jsx("h3", { className: "text-lg font-display font-bold text-brand-ink", children: "Class Details" }), _jsx("button", { onClick: onClose, className: "p-1 hover:bg-gray-100 rounded-full", "aria-label": "Close", children: _jsx(X, { className: "w-5 h-5 text-brand-muted" }) })] }), _jsxs("div", { className: "space-y-6", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs font-bold uppercase text-brand-muted mb-1", children: "Class Name" }), _jsx("p", { className: "text-brand-ink font-medium", children: cls.name })] }), _jsxs("div", { className: "grid grid-cols-2 gap-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs font-bold uppercase text-brand-muted mb-1", children: "Subject" }), _jsx("p", { className: "text-brand-ink font-medium", children: cls.subject })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs font-bold uppercase text-brand-muted mb-1", children: "Grade" }), _jsxs("p", { className: "text-brand-ink font-medium", children: ["Grade ", cls.grade] })] })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs font-bold uppercase text-brand-muted mb-1", children: "Teacher" }), _jsxs("select", { value: selectedTeacherId, onChange: (e) => setSelectedTeacherId(e.target.value), onBlur: handleTeacherChange, className: "w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary", children: [_jsx("option", { value: "", children: "Unassigned" }), teachers?.map((t) => (_jsxs("option", { value: t.id, children: [t.first_name, " ", t.last_name] }, t.id)))] })] }), _jsxs("div", { children: [_jsxs("div", { className: "flex items-center justify-between mb-2", children: [_jsx("label", { className: "text-xs font-bold uppercase text-brand-muted", children: "Enrolled Students" }), _jsx("button", { onClick: () => setIsEnrollOpen(!isEnrollOpen), className: "text-xs text-brand-primary hover:underline font-medium", children: "+ Enroll" })] }), isEnrollOpen && (_jsxs("div", { className: "mb-3 p-3 bg-brand-light rounded-lg border border-brand-mid", children: [_jsx("p", { className: "text-xs text-brand-muted mb-2", children: "Select students to enroll:" }), _jsx("div", { className: "max-h-40 overflow-y-auto space-y-1", children: students.map((s) => (_jsxs("label", { className: "flex items-center gap-2 text-sm text-brand-ink", children: [_jsx("input", { type: "checkbox", checked: selectedStudents.includes(s.id), onChange: () => toggleStudent(s.id), className: "rounded border-brand-border" }), s.first_name, " ", s.last_name] }, s.id))) }), selectedStudents.length > 0 && (_jsxs(Button, { variant: "primary", size: "sm", onClick: handleEnroll, className: "mt-2 w-full", children: ["Enroll ", selectedStudents.length, " student(s)"] }))] })), enrolledStudents.length > 0 ? (_jsxs("div", { className: "space-y-2", children: [enrolledStudents.map((s) => (_jsxs("div", { className: "flex items-center justify-between p-2 bg-gray-50 rounded-lg", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsxs("div", { className: "w-6 h-6 rounded-full bg-brand-light text-brand-primary text-xs font-bold flex items-center justify-center", children: [s.first_name[0], s.last_name[0]] }), _jsxs("span", { className: "text-sm text-brand-ink", children: [s.first_name, " ", s.last_name] })] }), _jsx(Badge, { variant: "success", children: "Active" })] }, s.id))), students.length > 10 && (_jsxs("p", { className: "text-xs text-brand-muted text-center", children: ["+", students.length - 10, " more students"] }))] })) : (_jsx("p", { className: "text-sm text-brand-muted", children: "No students enrolled yet." }))] }), _jsx("div", { className: "pt-4 border-t border-brand-border", children: _jsx(Button, { variant: "danger", size: "sm", onClick: onDeactivate, className: "w-full", children: "Deactivate class" }) })] })] }) })] }));
}
export function ClassManagement() {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedClass, setSelectedClass] = useState(null);
    const { data: classes, isLoading: classesLoading } = useSchoolClasses();
    const { data: teachers } = useSchoolUsers("TEACHER");
    const { data: students } = useSchoolUsers("STUDENT");
    const updateClass = useUpdateClass();
    const enrollStudents = useEnrollStudents(selectedClass?.id || "");
    const handleUpdateTeacher = (teacherId) => {
        if (selectedClass) {
            updateClass.mutate({
                classId: selectedClass.id,
                teacher_id: teacherId || undefined,
            });
            setSelectedClass({ ...selectedClass, teacher_id: teacherId });
        }
    };
    const handleEnrollStudents = (studentIds) => {
        if (selectedClass) {
            enrollStudents.mutate({ student_ids: studentIds });
        }
    };
    const handleDeactivate = () => {
        if (selectedClass) {
            setSelectedClass(null);
        }
    };
    return (_jsx(DashboardLayout, { variant: "school-admin", pageTitle: "Classes", pageSubtitle: "Manage classes, assign teachers, and enroll students", topNavAction: _jsxs(Button, { variant: "primary", size: "sm", onClick: () => setIsModalOpen(true), children: [_jsx(Plus, { className: "w-4 h-4 mr-1" }), "Create class"] }), children: _jsxs("div", { className: "space-y-6", children: [_jsx(Card, { variant: "default", className: "bg-white border-role-school-border overflow-hidden", children: classesLoading ? (_jsx("div", { className: "p-8 text-center text-brand-muted", children: "Loading..." })) : classes && classes.length > 0 ? (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-brand-border text-left", children: [_jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Class" }), _jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Subject" }), _jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Grade" }), _jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Teacher" }), _jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Students" })] }) }), _jsx("tbody", { children: classes.map((cls) => (_jsxs("tr", { onClick: () => setSelectedClass(cls), className: "border-b border-brand-border-soft last:border-0 hover:bg-brand-light/30 cursor-pointer", children: [_jsx("td", { className: "py-3 px-4", children: _jsxs("div", { className: "flex items-center gap-2", children: [_jsx(BookOpen, { className: "w-4 h-4 text-brand-primary" }), _jsx("span", { className: "text-sm font-medium text-brand-ink", children: cls.name })] }) }), _jsx("td", { className: "py-3 px-4 text-sm text-brand-body", children: cls.subject }), _jsx("td", { className: "py-3 px-4 text-sm text-brand-body", children: cls.grade }), _jsx("td", { className: "py-3 px-4 text-sm text-brand-body", children: cls.teacher_name || "Unassigned" }), _jsx("td", { className: "py-3 px-4 text-sm text-brand-body", children: cls.student_count })] }, cls.id))) })] }) })) : (_jsx("div", { className: "p-8 text-center text-brand-muted", children: "No classes yet. Create your first class to get started." })) }), _jsx(CreateClassModal, { isOpen: isModalOpen, onClose: () => setIsModalOpen(false), onCreated: () => { } }), selectedClass && (_jsx(ClassDetailPanel, { cls: selectedClass, teachers: teachers || [], students: students || [], onClose: () => setSelectedClass(null), onUpdateTeacher: handleUpdateTeacher, onEnrollStudents: handleEnrollStudents, onDeactivate: handleDeactivate }))] }) }));
}
