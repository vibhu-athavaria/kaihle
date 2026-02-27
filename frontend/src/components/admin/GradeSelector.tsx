import React from 'react';
import { Grade } from '../../hooks/useSchoolAdmin';

interface GradeSelectorProps {
  grades?: Grade[];
  selectedGradeId?: string | null;
  onChange: (gradeId: string) => void;
  placeholder?: string;
  error?: string;
}

const GradeSelector: React.FC<GradeSelectorProps> = ({
  grades = [],
  selectedGradeId,
  onChange,
  placeholder = "Select a grade",
  error
}) => {
  return (
    <div className="grade-selector">
      <select
        value={selectedGradeId || ''}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full px-3 py-2 border rounded-md ${
          error ? 'border-red-500' : 'border-gray-300'
        } focus:outline-none focus:ring-2 focus:ring-blue-500`}
      >
        <option value="">{placeholder}</option>
        {grades.map((grade) => (
          <option key={grade.id} value={grade.id}>
            {grade.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="mt-1 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
};

export default GradeSelector;
