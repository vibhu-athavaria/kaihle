import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, OnboardingRoute } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";
export default function App() {
    return (_jsx(BrowserRouter, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(LoginPage, {}) }), _jsx(Route, { path: "/student/onboarding", element: _jsx(PrivateRoute, { children: _jsx("div", { className: "p-8 text-gray-500", children: "Student onboarding \u2014 coming in M0-6-T4" }) }) }), _jsx(Route, { path: "/student/*", element: _jsx(PrivateRoute, { children: _jsx(OnboardingRoute, { children: _jsx("div", { className: "p-8 text-gray-500", children: "Student dashboard \u2014 coming in M2" }) }) }) }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/login", replace: true }) })] }) }));
}
