import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { http } from "@/lib/http";
import { GRADES }  from '../lib/utils';
import { Breadcrumb } from '../components/ui/Breadcrumb';
import { Users } from 'lucide-react';
import LearningProfileForm from '../components/LearningProfileForm';



interface AddChildForm {
  full_name: string;
  age: number;
  grade: number;
  username: string;
  password: string;
}

export const AddChild: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [newChild, setNewChild] = useState<any>(null);
  const { register, handleSubmit, formState: { errors } } = useForm<AddChildForm>();


  const onSubmit = async (data: AddChildForm) => {
    setLoading(true);
    try {

      // 2. Proceed with creating child if username available
      const response = await http.post('/api/v1/users/me/students', {
        name: data.full_name,
        age: data.age,
        grade_level: data.grade,
        username: data.username,
        password: data.password,
      });

      const child = response.data;
      setNewChild(child);
      setShowProfileForm(true);
    } catch (err) {
      console.error('Failed to create child profile:', err);
      alert('Failed to create child profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSubmit = async (profileData: {
    interests: string[];
    preferred_format: string;
    preferred_session_length: number;
  }) => {
    try {
      const response = await http.patch(`/api/v1/students/${newChild.id}/learning-profile`,
        profileData
      );
      const updatedChildFromServer = response.data;

      // Read existing children
      const existingChildren = JSON.parse(
        localStorage.getItem('children') || '[]'
      );

      // Replace updated student using server response
      const updatedChildren = existingChildren.map((c: any) =>
        c.id === updatedChildFromServer.id
          ? updatedChildFromServer
          : c
      );

      // Persist server-truth state
      localStorage.setItem('children', JSON.stringify(updatedChildren));
      localStorage.setItem(
        'currentChild',
        JSON.stringify(updatedChildFromServer)
      );

      navigate('/dashboard');
    } catch (err) {
      console.error('Failed to save learning profile:', err);
      alert('Failed to save learning profile. Please try again.');
    }
  };

  const handleProfileSkip = () => {
    // Update local storage
    const existingChildren = JSON.parse(localStorage.getItem('children') || '[]');
    existingChildren.push(newChild);
    localStorage.setItem('children', JSON.stringify(existingChildren));
    localStorage.setItem('currentChild', JSON.stringify(newChild));
    navigate('/dashboard');
  };


  if (showProfileForm && newChild) {
    return (
      <div className="min-h-screen bg-blue-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl w-full mx-auto">
          <div className="mb-6">
            <Breadcrumb role="parent" items={[{ label: 'Add Child', icon: Users }, { label: 'Learning Profile' }]} />
          </div>
          <LearningProfileForm
            onSubmit={handleProfileSubmit}
            onSkip={handleProfileSkip}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full mx-auto">
        <div className="mb-6">
          <Breadcrumb role="parent" items={[{ label: 'Add Child', icon: Users }]} />
        </div>
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">
              Tell us about your child
            </h2>
            <p className="text-gray-600">
              Let's get them started on their learning adventure.
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Full Name */}
            <div>
              <input
                {...register('full_name', {
                  required: 'Full name is required',
                  minLength: {
                    value: 2,
                    message: 'Name must be at least 2 characters'
                  }
                })}
                type="text"
                placeholder="Full Name"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
              />
              {errors.full_name && (
                <p className="mt-1 text-sm text-red-600">{errors.full_name.message}</p>
              )}
            </div>

            {/* Username */}
            <div>
              <input
                {...register('username', {
                  required: 'Username is required',
                  minLength: {
                    value: 3,
                    message: 'Username must be at least 3 characters'
                  }
                })}
                type="text"
                placeholder="Username"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
              />
              {errors.username && (
                <p className="mt-1 text-sm text-red-600">{errors.username.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <input
                {...register('password', {
                  required: 'Password is required',
                  minLength: {
                    value: 6,
                    message: 'Password must be at least 6 characters'
                  }
                })}
                type="password"
                placeholder="Password"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
              />
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>

            {/* Age */}
            <div>
              <input
                {...register('age', {
                  required: 'Age is required',
                  min: { value: 5, message: 'Age must be at least 5' },
                  max: { value: 18, message: 'Age must be 18 or under' }
                })}
                type="number"
                placeholder="Age"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
              />
              {errors.age && (
                <p className="mt-1 text-sm text-red-600">{errors.age.message}</p>
              )}
            </div>

            {/* Grade */}
            <div>
              <select
                {...register('grade', { required: 'Grade selection is required' })}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white"
                defaultValue=""
              >
                <option value="" disabled>Select grade</option>
                {GRADES.map((grade) => (
                  <option key={grade.value} value={grade.value}>{grade.label}</option>
                ))}
              </select>
              {errors.grade && (
                <p className="mt-1 text-sm text-red-600">{errors.grade.message}</p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 outline-none transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating Profile...' : 'Continue'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
