import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSchoolAdmin, Grade } from '../../hooks/useSchoolAdmin';
import { useAuth } from '../../contexts/AuthContext';
import GradeSelector from '../../components/admin/GradeSelector';

const PendingRegistrations: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const schoolId = user?.school_id;
  const { loading, error, registrations, grades, fetchRegistrations, approveRegistration, rejectRegistration } = useSchoolAdmin(schoolId);

  const [selectedGrades, setSelectedGrades] = useState<Record<string, string>>({});
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [rejectReason, setRejectReason] = useState<string>('');
  const [selectedRegistrationId, setSelectedRegistrationId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string>('');

  useEffect(() => {
    fetchRegistrations();
  }, [schoolId]);

  const handleGradeChange = (registrationId: string, gradeId: string): void => {
    setSelectedGrades({ ...selectedGrades, [registrationId]: gradeId });
    setActionError('');
  };

  const handleApprove = async (registrationId: string): Promise<void> => {
    const gradeId = selectedGrades[registrationId];
    if (!gradeId) {
      setActionError('Please select a grade before approving');
      return;
    }
    try {
      await approveRegistration(registrationId, gradeId);
      setSelectedGrades({ ...selectedGrades, [registrationId]: '' });
    } catch (err: any) {
      setActionError(err.message);
    }
  };

  const handleRejectClick = (registrationId: string): void => {
    setSelectedRegistrationId(registrationId);
    setShowRejectModal(true);
  };

  const handleRejectConfirm = async (): Promise<void> => {
    if (!selectedRegistrationId) return;
    try {
      await rejectRegistration(selectedRegistrationId, rejectReason);
      setShowRejectModal(false);
      setRejectReason('');
      setSelectedRegistrationId(null);
    } catch (err: any) {
      setActionError(err.message);
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
            <h1 className="text-3xl font-bold text-gray-900">Pending Registrations</h1>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
            Error loading registrations: {error}
          </div>
        )}

        {actionError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
            {actionError}
          </div>
        )}

        {registrations.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">No pending registrations</h3>
            <p className="mt-2 text-gray-500">Students will appear here once they register with your school code.</p>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {registrations.map((registration) => (
                  <tr key={registration.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{registration.full_name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{registration.email}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">
                        {new Date(registration.created_at).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <GradeSelector
                        grades={grades}
                        selectedGradeId={selectedGrades[registration.id]}
                        onChange={(gradeId) => handleGradeChange(registration.id, gradeId)}
                        placeholder="Select grade"
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex space-x-2">
                        <button
                          onClick={() => handleApprove(registration.id)}
                          className="px-3 py-1 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleRejectClick(registration.id)}
                          className="px-3 py-1 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
                        >
                          Reject
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Reject Modal */}
        {showRejectModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full">
              <h3 className="text-lg font-bold mb-4">Reject Registration</h3>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Reason for rejection (optional)"
                className="w-full border border-gray-300 rounded-md p-3 mb-4"
                rows={3}
              />
              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => setShowRejectModal(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRejectConfirm}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                >
                  Reject
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PendingRegistrations;
