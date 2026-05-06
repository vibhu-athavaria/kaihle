export const ACADEMIC_YEAR_REGEX = /^\d{4}-\d{4}$/;

export function currentAcademicYear(): string {
  const year = new Date().getFullYear();
  const month = new Date().getMonth() + 1;
  return month >= 8 ? `${year}-${year + 1}` : `${year - 1}-${year}`;
}
