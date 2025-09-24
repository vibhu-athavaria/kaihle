import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, AuthContextType } from '../types';
import axios from 'axios';
import config from '../config';

axios.defaults.baseURL = config.backendUrl;

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkSession = async () => {
      const token = localStorage.getItem('access_token');
      const tokenType = localStorage.getItem('token_type');
      if (token && tokenType) {
        axios.defaults.headers.common['Authorization'] = `${tokenType} ${token}`;
        try {
          const me = await axios.get('/api/v1/users/me');
          setUser(me.data);
        } catch (err) {
          console.error('Session expired, logging out');
          signOut();
        }
      }
      setLoading(false);
    };

    setTimeout(checkSession, 100);
  }, []);

  // ---------- SIGNUP (Parents only for now) ----------
  // ---------- SIGNUP (Parents only for now) ----------
  const signUpParent = async (email: string, password: string) => {
    setLoading(true);
    try {
      // 1. Check if email already exists
      const check = await axios.get(`/api/v1/users/check-email`, {
        params: { email }
      });

      if (check.data.exists) {
        throw new Error('This email is already registered. Please log in instead.');
      }

      // 2. Proceed with signup if not exists
      const response = await axios.post('/api/v1/auth/signup', {
        email: email,
        username: email,      // using email as username for parents
        password: password,
        full_name: email,     // you might replace this with an actual form field
        role: 'parent'
      });

      const newUser = response.data;
      setUser(newUser);
      localStorage.setItem('user', JSON.stringify(newUser));
    } catch (error: any) {
      const errorMessage = error.response?.data?.message || error.message || 'Failed to create account';
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };


  // ---------- LOGIN (Parent) ----------
  const signInParent = async (email: string, password: string) => {
    return signInCommon(email, password, 'parent');
  };

  // ---------- LOGIN (Student) ----------
  const signInStudent = async (username: string, password: string) => {
    return signInCommon(username, password, 'student');
  };

  // ---------- COMMON LOGIN HANDLER ----------
  const signInCommon = async (identifier: string, password: string, role: 'parent' | 'student') => {
    setLoading(true);
    try {
      const response = await axios.post('/api/v1/auth/login', {
        'identifier': identifier,
        'password': password,
        'role': role
      });
      const { access_token, token_type } = response.data;

      localStorage.setItem('access_token', access_token);
      localStorage.setItem('token_type', token_type);

      axios.defaults.headers.common['Authorization'] = `${token_type} ${access_token}`;

      const me = await axios.get('/api/v1/users/me');
      setUser(me.data);

      localStorage.setItem('user', JSON.stringify(me.data));
    } catch (error: any) {
      const errorMessage = error.response?.data?.message || 'Failed to sign in';
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // ---------- LOGOUT ----------
  const signOut = async () => {
    setUser(null);
    localStorage.removeItem('user');
    localStorage.removeItem('access_token');
    localStorage.removeItem('token_type');
  };

  return (
    <AuthContext.Provider
      value={{ user, signUpParent, signInParent, signInStudent, signOut, loading }}
    >
      {children}
    </AuthContext.Provider>
  );
};
