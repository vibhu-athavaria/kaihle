import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useForm } from 'react-hook-form';

interface LoginForm {
  username: string;
  password: string;
}

export const StudentLogin: React.FC = () => {
  const { signInStudent, loading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>();

  const onSubmit = async (data: LoginForm) => {
    setError('');
    try {
      const user = await signInStudent(data.username, data.password);
      if (user?.student_profile?.registration_completed_at) {
        navigate('/child-dashboard');
      } else {
        navigate('/complete-profile');
      }
    } catch (err) {
      setError('Invalid username or password.');
    }
  };

  return (
    <div className="min-h-screen bg-blue-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">
              Welcome back Student
            </h2>
            <p className="text-gray-600">
              Access your student account
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div>
              <input
                {...register('username', {
                  required: 'Username is required',
                })}
                type="text"
                placeholder="Username"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
              />
              {errors.username && (
                <p className="mt-1 text-sm text-red-600">{errors.username.message}</p>
              )}
            </div>

            <div>
              <input
                {...register('password', {
                  required: 'Password is required'
                })}
                type="password"
                placeholder="Password"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
              />
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 outline-none transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing In...' : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 text-center space-y-2">
            <Link
              to="/signup"
              className="text-blue-600 hover:text-blue-700 font-medium transition-colors block"
            >
              Don't have an account? Sign up
            </Link>
            <Link
              to="/parent-login"
              className="text-gray-600 hover:text-blue-700 text-sm block"
            >
              For parents, click here to login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
