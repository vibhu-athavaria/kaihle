import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

// Map numeric grade levels for backend
export const GRADES = [
  { label: '5th Grade', value: 5 },
  { label: '6th Grade', value: 6 },
  { label: '7th Grade', value: 7 },
  { label: '8th Grade', value: 8 },
  { label: '9th Grade', value: 9 },
  { label: '10th Grade', value: 10 },
  { label: '11th Grade', value: 11 },
  { label: '12th Grade', value: 12 },
];

export const SUBJECTS = ['Math', 'Science', 'English', 'Humanities'];

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}


