import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useForm } from 'react-hook-form';

interface StudentSignUpForm {
  full_name: string;
  email: string;
  password: string;
  confirmPassword: string;
  school_code: string;
}

export const StudentSignUp: React.FC = () => {
  const { signUpStudent, loading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [schoolName, setSchoolName] = useState('');

  const { register, handleSubmit, watch, formState: { errors } } = useForm<StudentSignUpForm>();
  const password = watch('password');

  const onSubmit = async (data: StudentSignUpForm) => {
    setError('');
    try {
      const result = await signUpStudent(
        data.full_name,
        data.email,
        data.password,
        data.school_code.toUpperCase()
      );

      setSchoolName(result.school_name);
      setSuccess(true);

      // Redirect to pending approval page after 3 seconds
      setTimeout(() => {
        navigate('/registration-pending', {
          state: {
            type: 'student',
            schoolName: result.school_name
          }
        });
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'Failed to register. Please try again.');
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-blue-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Registration Submitted!</h2>
            <p className="text-gray-600 mb-4">
              Your registration request for <strong>{schoolName}</strong> has been submitted.
              The school administrator will review and approve your registration.
            </p>
            <p className="text-sm text-gray-500">Redirecting...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">
              Student Registration
            </h2>
            <p className="text-gray-600">
              Join your school on Kaihle and start your learning journey.
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
              <input
                {...register('full_name', {
                  required: 'Full name is required',
                  minLength: { value: 2, message: 'Name must be at least 2 characters' }
                })}
                type="text"
                placeholder="Jane Doe"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
              />
              {errors.full_name && (
                <p className="mt-1 text-sm text-red-600">{errors.full_name.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
              <input
                {...register('email', {
                  required: 'Email is required',
                  pattern: {
                    value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                    message: 'Invalid email address'
                  }
                })}
                type="email"
                placeholder="student@email.com"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
              />
              {errors.email && (
                <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">School Code</label>
              <input
                {...register('school_code', {
                  required: 'School code is required',
                  minLength: { value: 8, message: 'School code must be 8 characters' },
                  maxLength: { value: 8, message: 'School code must be 8 characters' },
                  pattern: {
                    value: /^[A-Z0-9]{8}$/i,
                    message: 'School code must be 8 alphanumeric characters'
                  }
                })}
                type="text"
                placeholder="ABCD1234"
                maxLength={8}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all uppercase"
              />
              {errors.school_code && (
                <p className="mt-1 text-sm text-red-600">{errors.school_code.message}</p>
              )}
              <p className="mt-1 text-xs text-gray-500">
                Enter the 8-character code provided by your school administrator
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input
                  {...register('password', {
                    required: 'Password is required',
                    minLength: { value: 8, message: 'Password must be at least 8 characters' }
                  })}
                  type="password"
                  placeholder="••••••••"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                />
                {errors.password && (
                  <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
                <input
                  {...register('confirmPassword', {
                    required: 'Please confirm your password',
                    validate: value => value === password || 'Passwords do not match'
                  })}
                  type="password"
                  placeholder="••••••••"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                />
                {errors.confirmPassword && (
                  <p className="mt-1 text-sm text-red-600">{errors.confirmPassword.message}</p>
                )}
              </div>
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 outline-none transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Registering...' : 'Register as Student'}
              </button>
            </div>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Already have an account?{' '}
              <Link
                to="/student-login"
                className="text-blue-600 hover:text-blue-700 font-medium transition-colors"
              >
                Log in
              </Link>
            </p>
          </div>

          <div className="mt-4 text-center">
            <Link
              to="/signup"
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              ← Back to signup options
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
