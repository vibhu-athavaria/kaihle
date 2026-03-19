/**
 * E2E Test Configuration
 *
 * Base URLs for different apps. Use environment variables in CI,
 * defaults for local development.
 */

const teacherPort = process.env.TEACHER_PORT || "3001";
const studentPort = process.env.STUDENT_PORT || "3002";
const parentPort = process.env.PARENT_PORT || "3003";

export const config = {
  teacherApp: `http://localhost:${teacherPort}`,
  studentApp: `http://localhost:${studentPort}`,
  parentApp: `http://localhost:${parentPort}`,
  apiUrl: process.env.API_URL || "http://localhost:8000",
};
