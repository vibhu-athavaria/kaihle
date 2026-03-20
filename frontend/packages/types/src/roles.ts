/** Role constants for the Kaihle platform.
 *
 * These values must match the UserRole enum in the backend.
 * Single source of truth - change here, not in individual components.
 */

export const UserRole = {
  STUDENT: "STUDENT",
  TEACHER: "TEACHER",
  SCHOOL_ADMIN: "SCHOOL_ADMIN",
  PARENT: "PARENT",
  KAIHLE_ADMIN: "KAIHLE_ADMIN",
} as const;

export type UserRole = (typeof UserRole)[keyof typeof UserRole];

/** Role group constants for common role combinations. */
export const RoleGroup = {
  ALL_ADMINS: [UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN] as const,
  ALL_STAFF: [
    UserRole.TEACHER,
    UserRole.SCHOOL_ADMIN,
    UserRole.KAIHLE_ADMIN,
  ] as const,
  ALL_ROLES: [
    UserRole.STUDENT,
    UserRole.TEACHER,
    UserRole.SCHOOL_ADMIN,
    UserRole.PARENT,
    UserRole.KAIHLE_ADMIN,
  ] as const,
} as const;

/** Helper functions for role checks. */
export const isStudent = (role: UserRole): boolean => role === UserRole.STUDENT;
export const isTeacher = (role: UserRole): boolean => role === UserRole.TEACHER;
export const isSchoolAdmin = (role: UserRole): boolean =>
  role === UserRole.SCHOOL_ADMIN;
export const isKaihleAdmin = (role: UserRole): boolean =>
  role === UserRole.KAIHLE_ADMIN;
export const isParent = (role: UserRole): boolean => role === UserRole.PARENT;
export const isAdmin = (role: UserRole): boolean =>
  role === UserRole.SCHOOL_ADMIN || role === UserRole.KAIHLE_ADMIN;
export const isStaff = (role: UserRole): boolean =>
  role === UserRole.TEACHER ||
  role === UserRole.SCHOOL_ADMIN ||
  role === UserRole.KAIHLE_ADMIN;
