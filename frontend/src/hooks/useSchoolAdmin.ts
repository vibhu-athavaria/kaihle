import { useState } from 'react';
import { http } from '../lib/http';

// Type definitions for school admin data
export interface DashboardStats {
  student_count: number;
  pending_registrations: number;
  teacher_count: number;
  avg_assessment_pct: number;
}

export interface Teacher {
  teacher_id: string;
  name: string;
  email: string;
  class_count: number;
}

export interface Student {
  student_id: string;
  name: string;
  email: string;
  grade: string;
  grade_id: string;
  diagnostic_status: 'completed' | 'in_progress' | 'not_started';
  avg_progress_pct: number;
}

export interface SchoolGrade {
  id: string;
  grade_id: string;
  label: string;
  student_count: number;
}

export interface Grade {
  id: string;
  label: string;
}

export interface Registration {
  id: string;
  full_name: string;
  email: string;
  created_at: string;
}

export interface InviteTeacherData {
  name: string;
  email: string;
}

export interface UseSchoolAdminReturn {
  loading: boolean;
  error: string | null;
  stats: DashboardStats | null;
  teachers: Teacher[];
  students: Student[];
  grades: SchoolGrade[];
  registrations: Registration[];
  fetchDashboard: () => Promise<void>;
  fetchTeachers: () => Promise<void>;
  inviteTeacher: (teacherData: InviteTeacherData) => Promise<Teacher>;
  deleteTeacher: (teacherId: string) => Promise<void>;
  fetchStudents: () => Promise<void>;
  fetchGrades: () => Promise<void>;
  updateStudentGrade: (studentId: string, gradeId: string) => Promise<Student>;
  fetchRegistrations: () => Promise<void>;
  approveRegistration: (registrationId: string, gradeId: string) => Promise<void>;
  rejectRegistration: (registrationId: string, reason: string) => Promise<void>;
}

export const useSchoolAdmin = (schoolId: string | undefined): UseSchoolAdminReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [grades, setGrades] = useState<SchoolGrade[]>([]);
  const [registrations, setRegistrations] = useState<Registration[]>([]);

  const fetchDashboard = async (): Promise<void> => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get<DashboardStats>(`/api/v1/schools/${schoolId}/dashboard`);
      setStats(response.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchTeachers = async (): Promise<void> => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get<Teacher[]>(`/api/v1/schools/${schoolId}/teachers`);
      setTeachers(response.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inviteTeacher = async (teacherData: InviteTeacherData): Promise<Teacher> => {
    if (!schoolId) throw new Error('School ID is required');
    setLoading(true);
    try {
      const response = await http.post<Teacher>(`/api/v1/schools/${schoolId}/teachers`, teacherData);
      setTeachers([...teachers, response.data]);
      return response.data;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const deleteTeacher = async (teacherId: string): Promise<void> => {
    if (!schoolId || !teacherId) return;
    setLoading(true);
    try {
      await http.delete(`/api/v1/schools/${schoolId}/teachers/${teacherId}`);
      setTeachers(teachers.filter(t => t.teacher_id !== teacherId));
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const fetchStudents = async (): Promise<void> => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get<Student[]>(`/api/v1/schools/${schoolId}/students`);
      setStudents(response.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchGrades = async (): Promise<void> => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get<SchoolGrade[]>(`/api/v1/schools/${schoolId}/grades`);
      setGrades(response.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateStudentGrade = async (studentId: string, gradeId: string): Promise<Student> => {
    if (!schoolId || !studentId) throw new Error('School ID and Student ID are required');
    setLoading(true);
    try {
      const response = await http.patch<Student>(`/api/v1/schools/${schoolId}/students/${studentId}/grade`, { grade_id: gradeId });
      setStudents(students.map(s => s.student_id === studentId ? { ...s, grade_id: gradeId } : s));
      return response.data;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const fetchRegistrations = async (): Promise<void> => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const response = await http.get<Registration[]>(`/api/v1/schools/${schoolId}/student-registrations`);
      setRegistrations(response.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const approveRegistration = async (registrationId: string, gradeId: string): Promise<void> => {
    if (!schoolId || !registrationId) return;
    setLoading(true);
    try {
      await http.patch(`/api/v1/schools/${schoolId}/student-registrations/${registrationId}/approve`, { grade_id: gradeId });
      setRegistrations(registrations.filter(r => r.id !== registrationId));
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const rejectRegistration = async (registrationId: string, reason: string): Promise<void> => {
    if (!schoolId || !registrationId) return;
    setLoading(true);
    try {
      await http.patch(`/api/v1/schools/${schoolId}/student-registrations/${registrationId}/reject`, { reason });
      setRegistrations(registrations.filter(r => r.id !== registrationId));
    } catch (err: any) {
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
