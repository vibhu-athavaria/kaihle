import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LearningProfileForm from '../components/LearningProfileForm';
import { http } from '@/lib/http';
import { Breadcrumb } from '../components/ui/Breadcrumb';
import { User } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const CompleteProfile: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [currentChild, setCurrentChild] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const childFromStorage = JSON.parse(localStorage.getItem('currentChild') || 'null');
    if (childFromStorage && childFromStorage.id) {
      setCurrentChild(childFromStorage);
    } else if (user?.role === 'student' && user.student_profile) {
      // For students, use their own profile
      setCurrentChild({
        id: user.student_profile.id,
        name: user.full_name,
        interests: user.student_profile.interests,
        preferred_format: user.student_profile.preferred_format,
        preferred_session_length: user.student_profile.preferred_session_length,
      });
    }
    setLoading(false);
  }, [user]);

  const handleProfileSubmit = async (profileData: {
    interests: string[];
    preferred_format: string;
    preferred_session_length: number;
  }) => {
    if (!currentChild?.id) {
      alert('No student selected. Please go back and select a child first.');
      navigate('/dashboard');
      return;
    }

    try {
      console.log('Submitting profile data:', {
        studentId: currentChild.id,
        profileData: { ...profileData, profile_completed: true }
      });

      const response = await http.patch(`/api/v1/students/${currentChild.id}/learning-profile`, {
        ...profileData
      });

      console.log('Profile saved successfully:', response.data);

      // Update local storage
      const updatedChild = { ...currentChild, ...profileData };
      localStorage.setItem('currentChild', JSON.stringify(updatedChild));
      // Update in children list
      const children = JSON.parse(localStorage.getItem('children') || '[]');
      const updatedChildren = children.map((c: any) => c.id === currentChild.id ? updatedChild : c);
      localStorage.setItem('children', JSON.stringify(updatedChildren));
      // Navigate to appropriate dashboard based on user role
      const dashboardRoute = user?.role === 'student' ? '/child-dashboard' : '/dashboard';
      navigate(dashboardRoute);
    } catch (err) {

      console.error('Failed to save learning profile:', err);
      console.error('Error response:', err.response?.data);
      console.error('Error status:', err.response?.status);

      let errorMessage = 'Failed to save learning profile. Please try again.';
      if (err.response?.data?.detail) {
        errorMessage = `Error: ${err.response.data.detail}`;
      } else if (err.response?.status === 403) {
        errorMessage = 'You do not have permission to update this student\'s profile.';
      } else if (err.response?.status === 404) {
        errorMessage = 'Student not found. Please refresh the page and try again.';
      } else if (err.message) {
        errorMessage = `Error: ${err.message}`;
      }

      alert(errorMessage);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading profile...</p>
        </div>
      </div>
    );
  }

  if (!currentChild) {
    return (
      <div className="min-h-screen bg-blue-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">No Student Selected</h2>
          <p className="text-gray-600 mb-6">Please select a child from your dashboard first.</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl w-full mx-auto">
        <div className="mb-6">
          <Breadcrumb role={user?.role === 'parent' ? 'parent' : 'student'} items={[{ label: 'Complete Profile', icon: User }]} />
        </div>
        <LearningProfileForm
          onSubmit={handleProfileSubmit}
          initialData={{
            interests: currentChild.interests,
            preferred_format: currentChild.preferred_format,
            preferred_session_length: currentChild.preferred_session_length
          }}
        />
      </div>
    </div>
  );
};

export default CompleteProfile;