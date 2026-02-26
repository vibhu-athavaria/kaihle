import { useState, useEffect } from 'react';
import { http } from '../lib/http';

export const useSchoolAdmin = (schoolId) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [grades, setGrades] = useState([]);
  const [registrations, setRegistrations] = useState([]);

  const fetchDashboard = async () => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get(`/api/v1/schools/${schoolId}/dashboard`);
      setStats(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchTeachers = async () => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get(`/api/v1/schools/${schoolId}/teachers`);
      setTeachers(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inviteTeacher = async (teacherData) => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.post(`/api/v1/schools/${schoolId}/teachers`, teacherData);
      setTeachers([...teachers, response.data]);
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const deleteTeacher = async (teacherId) => {
    if (!schoolId || !teacherId) return;
    setLoading(true);
    try {
      await http.delete(`/api/v1/schools/${schoolId}/teachers/${teacherId}`);
      setTeachers(teachers.filter(t => t.teacher_id !== teacherId));
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const fetchStudents = async () => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get(`/api/v1/schools/${schoolId}/students`);
      setStudents(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchGrades = async () => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get(`/api/v1/schools/${schoolId}/grades`);
      setGrades(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateStudentGrade = async (studentId, gradeId) => {
    if (!schoolId || !studentId) return;
    setLoading(true);
    try {
      const response = await http.patch(`/api/v1/schools/${schoolId}/students/${studentId}/grade`, { grade_id: gradeId });
      setStudents(students.map(s => s.student_id === studentId ? { ...s, grade_id: gradeId } : s));
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const fetchRegistrations = async () => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get(`/api/v1/schools/${schoolId}/student-registrations`);
      setRegistrations(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const approveRegistration = async (registrationId, gradeId) => {
    if (!schoolId || !registrationId) return;
    setLoading(true);
    try {
      const response = await http.patch(`/api/v1/schools/${schoolId}/student-registrations/${registrationId}/approve`, { grade_id: gradeId });
      setRegistrations(registrations.filter(r => r.id !== registrationId));
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const rejectRegistration = async (registrationId, reason) => {
    if (!schoolId || !registrationId) return;
    setLoading(true);
    try {
      const response = await http.patch(`/api/v1/schools/${schoolId}/student-registrations/${registrationId}/reject`, { reason });
      setRegistrations(registrations.filter(r => r.id !== registrationId));
      return response.data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return {
    loading,
    error,
    stats,
    teachers,
    students,
    grades,
    registrations,
    fetchDashboard,
    fetchTeachers,
    inviteTeacher,
    deleteTeacher,
    fetchStudents,
    fetchGrades,
    updateStudentGrade,
    fetchRegistrations,
    approveRegistration,
    rejectRegistration
  };
};

export default useSchoolAdmin;
