import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { http } from '../../lib/http';
import { useAuth } from '../../contexts/AuthContext';

const StudentDetail = () => {
  const navigate = useNavigate();
  const { studentId } = useParams();
  const { user } = useAuth();
  const schoolId = user?.school_id;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [student, setStudent] = useState(null);
  const [progress, setProgress] = useState([]);

  useEffect(() => {
    if (studentId && schoolId) {
      fetchStudentDetails();
    }
  }, [studentId, schoolId]);

  const fetchStudentDetails = async () => {
    setLoading(true);
    try {
      const [studentRes, progressRes] = await Promise.all([
        http.get(`/api/v1/schools/${schoolId}/students/${studentId}`),
        http.get(`/api/v1/schools/${schoolId}/students/${studentId}/progress`).catch(() => ({ data: { subtopics: [] } }))
      ]);
      setStudent(studentRes.data);
      setProgress(progressRes.data.subtopics || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    if (!status) {
      return (
        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
          Not Started
        </span>
      );
    }
    const statusConfig = {
      'completed': { bg: 'bg-green-100', text: 'text-green-800', label: 'Completed' },
      'in_progress': { bg: 'bg-blue-100', text: 'text-blue-800', label: 'In Progress' },
      'not_started': { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Not Started' }
    };
    const config = statusConfig[status] || statusConfig['not_started'];
    return (
      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${config.bg} ${config.text}`}>
        {config.label}
      </span>
    );
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

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            Error loading student: {error}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <button
            onClick={() => navigate('/admin/students')}
            className="text-blue-600 hover:text-blue-800 mb-2"
          >
            &larr; Back to Students
          </button>
          <h1 className="text-3xl font-bold text-gray-900">Student Details</h1>
        </div>

        {/* Student Info Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div>
              <p className="text-sm text-gray-500">Name</p>
              <p className="text-lg font-medium text-gray-900">{student?.name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Email</p>
              <p className="text-lg font-medium text-gray-900">{student?.email}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Grade</p>
              <p className="text-lg font-medium text-gray-900">{student?.grade || 'Not assigned'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Diagnostic Status</p>
              <div className="mt-1">{getStatusBadge(student?.diagnostic_status)}</div>
            </div>
          </div>
        </div>

        {/* Progress Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-500">Plans Linked</p>
            <p className="text-3xl font-bold text-gray-900">{student?.plans_linked || 0} / {student?.plans_total || 0}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-500">Average Progress</p>
            <p className="text-3xl font-bold text-gray-900">{student?.avg_progress_pct || 0}%</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-500">Classes Enrolled</p>
            <p className="text-3xl font-bold text-gray-900">{student?.classes_enrolled || 0}</p>
          </div>
        </div>

        {/* Subtopics Progress */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Subject Progress</h2>
          </div>
          {progress.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              No progress data available yet. The student needs to complete their diagnostic assessment first.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subtopic</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time Spent</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Completed</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {progress.map((item) => (
                  <tr key={item.class_subtopic_id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{item.subtopic_name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(item.status)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">
                        {item.time_spent_minutes ? `${item.time_spent_minutes} min` : '-'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">
                        {item.completed_at ? new Date(item.completed_at).toLocaleDateString() : '-'}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

export default StudentDetail;
