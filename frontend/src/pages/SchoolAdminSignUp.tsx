import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useForm } from 'react-hook-form';
import { http } from '@/lib/http';

interface Curriculum {
  id: string;
  name: string;
  code: string | null;
  country: string | null;
}

interface SchoolAdminSignUpForm {
  admin_name: string;
  admin_email: string;
  password: string;
  confirmPassword: string;
  school_name: string;
  country: string;
  curriculum_id: string;
}

export const SchoolAdminSignUp: React.FC = () => {
  const { signUpSchoolAdmin, loading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [loadingCurricula, setLoadingCurricula] = useState(true);

  const { register, handleSubmit, watch, formState: { errors } } = useForm<SchoolAdminSignUpForm>();
  const password = watch('password');

  // Fetch curricula on mount
  useEffect(() => {
    const fetchCurricula = async () => {
      try {
        const response = await http.get<Curriculum[]>('/api/v1/subjects/curricula');
        setCurricula(response.data);
      } catch (err) {
        console.error('Failed to fetch curricula:', err);
        // Use default curricula if API fails
        setCurricula([
          { id: 'default-1', name: 'Cambridge (CAIE)', code: 'CAIE', country: 'International' },
          { id: 'default-2', name: 'IB (International Baccalaureate)', code: 'IB', country: 'International' },
          { id: 'default-3', name: 'CBSE', code: 'CBSE', country: 'India' },
          { id: 'default-4', name: 'Common Core (US)', code: 'CCSS', country: 'United States' },
        ]);
      } finally {
        setLoadingCurricula(false);
      }
    };
    fetchCurricula();
  }, []);

  const onSubmit = async (data: SchoolAdminSignUpForm) => {
    setError('');
    try {
      const result = await signUpSchoolAdmin(
        data.admin_name,
        data.admin_email,
        data.password,
        data.school_name,
        data.country,
        data.curriculum_id
      );

      // Show success message
      setSuccess(true);

      // Redirect to pending approval page after 3 seconds
      setTimeout(() => {
        navigate('/registration-pending', {
          state: {
            type: 'school',
            schoolId: result.school_id
          }
        });
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'Failed to register school. Please try again.');
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
              Your school registration has been submitted and is pending approval.
              You will receive an email once your school is approved.
            </p>
            <p className="text-sm text-gray-500">Redirecting...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-lg w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">
              Register Your School
            </h2>
            <p className="text-gray-600">
              Create a school admin account and register your school on Kaihle.
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Admin Information */}
            <div className="border-b border-gray-200 pb-5 mb-5">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Administrator Information</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                  <input
                    {...register('admin_name', {
                      required: 'Full name is required',
                      minLength: { value: 2, message: 'Name must be at least 2 characters' }
                    })}
                    type="text"
                    placeholder="John Doe"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                  />
                  {errors.admin_name && (
                    <p className="mt-1 text-sm text-red-600">{errors.admin_name.message}</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                  <input
                    {...register('admin_email', {
                      required: 'Email is required',
                      pattern: {
                        value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                        message: 'Invalid email address'
                      }
                    })}
                    type="email"
                    placeholder="admin@school.edu"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                  />
                  {errors.admin_email && (
                    <p className="mt-1 text-sm text-red-600">{errors.admin_email.message}</p>
                  )}
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
              </div>
            </div>

            {/* School Information */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">School Information</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">School Name</label>
                  <input
                    {...register('school_name', {
                      required: 'School name is required',
                      minLength: { value: 3, message: 'School name must be at least 3 characters' }
                    })}
                    type="text"
                    placeholder="Springfield International School"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                  />
                  {errors.school_name && (
                    <p className="mt-1 text-sm text-red-600">{errors.school_name.message}</p>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
                    <select
                      {...register('country', { required: 'Country is required' })}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                    >
                      <option value="">Select Country</option>
                      <option value="Indonesia">Indonesia</option>
                      <option value="Singapore">Singapore</option>
                      <option value="Malaysia">Malaysia</option>
                      <option value="India">India</option>
                      <option value="United States">United States</option>
                      <option value="United Kingdom">United Kingdom</option>
                      <option value="Australia">Australia</option>
                      <option value="Other">Other</option>
                    </select>
                    {errors.country && (
                      <p className="mt-1 text-sm text-red-600">{errors.country.message}</p>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Curriculum</label>
                    <select
                      {...register('curriculum_id', { required: 'Curriculum is required' })}
                      disabled={loadingCurricula}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all disabled:bg-gray-100"
                    >
                      <option value="">Select Curriculum</option>
                      {curricula.map((curriculum) => (
                        <option key={curriculum.id} value={curriculum.id}>
                          {curriculum.name}
                        </option>
                      ))}
                    </select>
                    {errors.curriculum_id && (
                      <p className="mt-1 text-sm text-red-600">{errors.curriculum_id.message}</p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading || loadingCurricula}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 outline-none transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Registering...' : 'Register School'}
              </button>
            </div>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Already have an account?{' '}
              <Link
                to="/school-admin-login"
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
