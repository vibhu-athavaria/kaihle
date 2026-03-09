import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";
export default function App() {
    return (_jsx(BrowserRouter, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(LoginPage, {}) }), _jsx(Route, { path: "/parent/*", element: _jsx(PrivateRoute, { children: _jsx("div", { className: "p-8 text-gray-500", children: "Parent dashboard \u2014 coming in M5" }) }) }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/login", replace: true }) })] }) }));
}
