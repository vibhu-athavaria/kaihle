export const Permission = {
  BILLING: "billing",
  USER_MANAGEMENT: "user_management",
  CURRICULUM: "curriculum",
  SCHOOL_SETTINGS: "school_settings",
  ANALYTICS: "analytics",
  ASSESSMENTS: "assessments",
  LESSON_PLANS: "lesson_plans",
  CONTENT_MANAGEMENT: "content_management",
} as const;

export type PermissionKey = (typeof Permission)[keyof typeof Permission];

export const PERMISSION_DEFAULTS: Record<PermissionKey, boolean> = {
  [Permission.BILLING]: true,
  [Permission.USER_MANAGEMENT]: true,
  [Permission.CURRICULUM]: true,
  [Permission.SCHOOL_SETTINGS]: true,
  [Permission.ANALYTICS]: true,
  [Permission.ASSESSMENTS]: true,
  [Permission.LESSON_PLANS]: true,
  [Permission.CONTENT_MANAGEMENT]: false,
};

export function hasPermission(
  permissions: Record<string, boolean> | null | undefined,
  permission: PermissionKey,
): boolean {
  const defaultValue = PERMISSION_DEFAULTS[permission];
  if (permissions == null) return defaultValue;
  return permissions[permission] ?? defaultValue;
}
