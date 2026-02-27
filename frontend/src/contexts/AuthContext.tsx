import React, { createContext, useContext, useEffect, useState } from "react";
import { User, AuthContextType } from "../types";
import { http } from "@/lib/http";
import { setAuthToken, clearAuthToken } from "@/lib/authToken";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

// Types for registration responses
interface SchoolAdminRegisterResponse {
  user_id: string;
  school_id: string;
  status: string;
}

interface StudentRegisterResponse {
  user_id: string;
  school_name: string;
  status: string;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const tokenType = localStorage.getItem("token_type");
    const savedUser = localStorage.getItem("user");

    // 1️⃣ If token exists, restore Authorization header immediately
    if (token && tokenType) {
      setAuthToken(token);
    }

    // If user exists in localStorage, restore it immediately (prevents logout flicker)
    if (savedUser) {
      setUser(JSON.parse(savedUser));
    }

    // Verify session with backend, but DO NOT log out on minor errors
    const verifySession = async () => {
      if (!token || !tokenType) {
        setLoading(false);
        return;
      }

      try {
        const me = await http.get("/api/v1/users/me");
        setUser(me.data);
        localStorage.setItem("user", JSON.stringify(me.data));
      } catch (err: any) {
        console.warn(
          "Could not verify session. Token might still be valid.",
          err
        );

        // Only logout if backend says token is invalid/expired
        if (err.response?.status === 401) {
          signOut();
        }
      } finally {
        setLoading(false);
      }
    };

    verifySession();
  }, []);

  // ---------- SIGNUP (Parents only for now) ----------
  const signUpParent = async (
    email: string,
    password: string,
    full_name: string
  ) => {
    setLoading(true);
    try {
      const response = await http.post("/api/v1/auth/signup", {
        email: email,
        username: email, // using email as username for parents
        password: password,
        full_name: full_name,
        role: "parent",
      });

      const newUser = response.data;
      setUser(newUser);
      localStorage.setItem("user", JSON.stringify(newUser));
    } catch (error: any) {
      const errorMessage =
        error.response?.data?.message ||
        error.message ||
        "Failed to create account";
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // ---------- SIGNUP (School Admin) ----------
  const signUpSchoolAdmin = async (
    adminName: string,
    adminEmail: string,
    password: string,
    schoolName: string,
    country: string,
    curriculumId: string
  ): Promise<SchoolAdminRegisterResponse> => {
    setLoading(true);
    try {
      const response = await http.post<SchoolAdminRegisterResponse>(
        "/api/v1/auth/register/school-admin",
        {
          admin_name: adminName,
          admin_email: adminEmail,
          password: password,
          school_name: schoolName,
          country: country,
          curriculum_id: curriculumId,
        }
      );

      return response.data;
    } catch (error: any) {
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Failed to register school";
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // ---------- SIGNUP (Student) ----------
  const signUpStudent = async (
    fullName: string,
    email: string,
    password: string,
    schoolCode: string
  ): Promise<StudentRegisterResponse> => {
    setLoading(true);
    try {
      const response = await http.post<StudentRegisterResponse>(
        "/api/v1/auth/register/student",
        {
          full_name: fullName,
          email: email,
          password: password,
          school_code: schoolCode,
        }
      );

      return response.data;
    } catch (error: any) {
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Failed to register as student";
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // ---------- LOGIN (Parent) ----------
  const signInParent = async (email: string, password: string) => {
    return signInCommon(email, password, "parent");
  };

  // ---------- LOGIN (Student) ----------
  const signInStudent = async (username: string, password: string) => {
    await signInCommon(username, password, "student");
    return user;
  };

  // ---------- LOGIN (School Admin) ----------
  const signInSchoolAdmin = async (email: string, password: string) => {
    return signInCommon(email, password, "school_admin");
  };

  // ---------- COMMON LOGIN HANDLER ----------
  const signInCommon = async (
    identifier: string,
    password: string,
    role: "parent" | "student" | "school_admin"
  ) => {
    setLoading(true);
    try {
      const response = await http.post("/api/v1/auth/login", {
        identifier: identifier,
        password: password,
        role: role,
      });
      const { access_token, token_type } = response.data;

      localStorage.setItem("access_token", access_token);
      localStorage.setItem("token_type", token_type);

      setAuthToken(access_token);

      const me = await http.get("/api/v1/users/me");
      setUser(me.data);

      localStorage.setItem("user", JSON.stringify(me.data));
    } catch (error: any) {
      const errorMessage = error.response?.data?.message || "Failed to sign in";
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // ---------- LOGOUT ----------
  const signOut = async () => {
    setUser(null);
    localStorage.clear();
    clearAuthToken();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        signUpParent,
        signUpSchoolAdmin,
        signUpStudent,
        signInParent,
        signInStudent,
        signInSchoolAdmin,
        signOut,
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
