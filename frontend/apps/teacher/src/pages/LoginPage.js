import { jsx as _jsx } from "react/jsx-runtime";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { LoginForm } from "@kaihle/ui";
export function LoginPage() {
    const { login, sendMagicLink } = useAuth();
    const navigate = useNavigate();
    const handleLogin = async (email, password) => {
        await login({ email, password });
        navigate("/teacher/dashboard");
    };
    return (_jsx(LoginForm, { onLogin: handleLogin, onMagicLink: sendMagicLink, logoLabel: "Teacher Portal" }));
}
