export { getMasteryStyle, scoreToPercent } from "./mastery";
export type { MasteryLabel, MasteryStyle } from "./mastery";

export { getSubjectColor, SUBJECT_COLORS } from "./subjects";

export { ACADEMIC_YEAR_REGEX, currentAcademicYear } from "./academic-year";

export {
  UserRole,
  RoleGroup,
  isStudent,
  isTeacher,
  isSchoolAdmin,
  isKaihleAdmin,
  isParent,
  isAdmin,
  isStaff,
} from "./roles";
export type { UserRole as UserRoleType } from "./roles";
