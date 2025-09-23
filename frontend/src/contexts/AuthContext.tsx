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
    // Simulate checking for existing session
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

    // Add a small delay to ensure proper loading state
    setTimeout(checkSession, 100);
  }, []);

  const signUp = async (email: string, password: string) => {
    setLoading(true);
    try {
      const response = await axios.post('/api/v1/auth/signup', {
        'email': email,
        'username': email,
        'password': password,
        'full_name': email,
        'role': 'parent'
      });

      const newUser = response.data; // Assuming the backend returns the created user object
      setUser(newUser);
      localStorage.setItem('user', JSON.stringify(newUser));
    } catch (error: any) {
      const errorMessage = error.response?.data?.message || 'Failed to create account';
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const signIn = async (email: string, password: string) => {
    setLoading(true);
    try {
      const response = await axios.post('/api/v1/auth/login', {
        'email': email,
        'password': password
      });
      const { access_token, token_type } = response.data;
      // Store the token in localStorage for future API calls
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('token_type', token_type);

      // Optionally, set the token in axios headers for authenticated requests
      axios.defaults.headers.common['Authorization'] = `${token_type} ${access_token}`;

      // Set the user state (if needed, you can fetch user details using the token)
      // ✅ Fetch current user from backend
      const me = await axios.get('/api/v1/users/me');
      setUser(me.data);

    // Store user in localStorage for reloads
    localStorage.setItem('user', JSON.stringify(me.data));
    } catch (error: any) {
      const errorMessage = error.response?.data?.message || 'Failed to sign in';
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const signOut = async () => {
    setUser(null);
    localStorage.removeItem('user');
  };

  return (
    <AuthContext.Provider value={{ user, signUp, signIn, signOut, loading }}>
      {children}
    </AuthContext.Provider>
  );
};