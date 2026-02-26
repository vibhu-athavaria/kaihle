import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { http } from '../../lib/http';
import { useAuth } from '../../contexts/AuthContext';

const ManageGrades = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const schoolId = user?.school_id;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [schoolGrades, setSchoolGrades] = useState([]);
  const [availableGrades, setAvailableGrades] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedGradeId, setSelectedGradeId] = useState('');

  useEffect(() => {
    fetchGrades();
  }, [schoolId]);

  const fetchGrades = async () => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get(`/api/v1/schools/${schoolId}/grades`);
      setSchoolGrades(response.data);

      // Fetch available curriculum grades
      const gradesResponse = await http.get('/api/v1/grades');
      const existingIds = response.data.map(g => g.grade_id);
      setAvailableGrades(gradesResponse.data.filter(g => !existingIds.includes(g.id)));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddGrade = async () => {
    if (!selectedGradeId) return;
    try {
      await http.post(`/api/v1/schools/${schoolId}/grades`, { grade_id: selectedGradeId });
      setShowAddModal(false);
      setSelectedGradeId('');
      fetchGrades();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteGrade = async (gradeId) => {
    if (!confirm('Are you sure you want to remove this grade? Students assigned to this grade will need to be reassigned.')) {
      return;
    }
    try {
      await http.delete(`/api/v1/schools/${schoolId}/grades/${gradeId}`);
      fetchGrades();
    } catch (err) {
      if (err.response?.status === 409) {
        setError('Cannot delete grade with students assigned. Please reassign students first.');
      } else {
        setError(err.message);
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-1/4 mb-8"></div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="h-64 bg-gray-200 rounded"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <button
              onClick={() => navigate('/admin/dashboard')}
              className="text-blue-600 hover:text-blue-800 mb-2"
            >
              ← Back to Dashboard
            </button>
            <h1 className="text-3xl font-bold text-gray-900">Manage Grades</h1>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Add Grade
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
            {error}
          </div>
        )}

        {schoolGrades.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">No grades added yet</h3>
            <p className="mt-2 text-gray-500">Add grades to your school to start enrolling students.</p>
            <button
              onClick={() => setShowAddModal(true)}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Add Your First Grade
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Students</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {schoolGrades.map((grade) => (
                  <tr key={grade.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{grade.label}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{grade.student_count || 0}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => handleDeleteGrade(grade.grade_id)}
                        className="text-red-600 hover:text-red-800 text-sm"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Add Grade Modal */}
        {showAddModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full">
              <h3 className="text-lg font-bold mb-4">Add Grade</h3>
              <select
                value={selectedGradeId}
                onChange={(e) => setSelectedGradeId(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-3 mb-4"
              >
                <option value="">Select a grade</option>
                {availableGrades.map((grade) => (
                  <option key={grade.id} value={grade.id}>
                    {grade.label}
                  </option>
                ))}
              </select>
              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddGrade}
                  disabled={!selectedGradeId}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300"
                >
                  Add Grade
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ManageGrades;