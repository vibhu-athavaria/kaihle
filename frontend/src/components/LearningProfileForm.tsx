import React, { useState } from 'react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { ChevronLeft, ChevronRight, Check } from 'lucide-react';

interface LearningProfileFormProps {
  onSubmit: (data: {
    interests: string[];
    preferred_format: string;
    preferred_session_length: number;
  }) => void;
  onSkip?: () => void;
  initialData?: {
    interests?: string[];
    preferred_format?: string;
    preferred_session_length?: number;
  };
}

const INTEREST_OPTIONS = [
  'Sports (Basketball, Soccer, Tennis, etc.)',
  'Music',
  'Gaming (Video games, Board games)',
  'Cooking/Food',
  'Art/Drawing',
  'Technology/Coding',
  'Animals/Nature',
  'Fashion',
  'Cars/Vehicles',
  'Movies/TV Shows',
  'Reading/Books',
  'Dance',
  'Space/Astronomy',
  'Magic/Tricks',
  'Superheroes',
  'Robots',
  'Dinosaurs',
  'Mysteries/Detective work',
  'Building/Construction',
  'Photography',
  'Writing/Stories',
  'Science Experiments',
  'Travel/Exploring',
  'Gardening',
  'Pets',
  'Collecting (stamps, cards, etc.)',
  'Martial Arts',
  'Theater/Acting',
  'Instruments (piano, guitar, etc.)',
  'Crafts',
  'Swimming',
  'Cycling',
  'Hiking/Outdoor activities',
  'Other'
];

const FORMAT_OPTIONS = [
  { value: 'Video', icon: '🎥' },
  { value: 'Text', icon: '📖' },
  { value: 'Interactive', icon: '🎮' },
  { value: 'Audio', icon: '🎧' }
];

const SESSION_LENGTH_OPTIONS = [
  { value: 15, label: '15 min' },
  { value: 30, label: '30 min' },
  { value: 45, label: '45 min' },
  { value: 60, label: '60 min' }
];

const LearningProfileForm: React.FC<LearningProfileFormProps> = ({
  onSubmit,
  onSkip,
  initialData = {}
}) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedInterests, setSelectedInterests] = useState<string[]>(
    initialData.interests || []
  );
  const [otherInterest, setOtherInterest] = useState('');
  const [preferredFormat, setPreferredFormat] = useState(
    initialData.preferred_format || ''
  );
  const [preferredSessionLength, setPreferredSessionLength] = useState(
    initialData.preferred_session_length || 30
  );

  const totalSteps = 3;

  const handleInterestToggle = (interest: string) => {
    setSelectedInterests(prev =>
      prev.includes(interest)
        ? prev.filter(i => i !== interest)
        : [...prev, interest]
    );
  };

  const handleFormatSelect = (format: string) => {
    setPreferredFormat(format);
  };

  const handleSessionLengthSelect = (length: number) => {
    setPreferredSessionLength(length);
  };

  const canProceedToNext = () => {
    switch (currentStep) {
      case 1:
        return selectedInterests.length > 0;
      case 2:
        return preferredFormat !== '';
      case 3:
        return true;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (canProceedToNext() && currentStep < totalSteps) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmit = () => {
    const interests = selectedInterests.includes('Other')
      ? [...selectedInterests.filter(i => i !== 'Other'), otherInterest].filter(Boolean)
      : selectedInterests;
    onSubmit({
      interests,
      preferred_format: preferredFormat,
      preferred_session_length: preferredSessionLength
    });
  };

  const renderStepIndicator = () => (
    <div className="flex items-center justify-center mb-6">
      {[1, 2, 3].map(step => (
        <div key={step} className="flex items-center">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
            step < currentStep
              ? 'bg-green-500 text-white'
              : step === currentStep
              ? 'bg-blue-500 text-white'
              : 'bg-gray-200 text-gray-600'
          }`}>
            {step < currentStep ? <Check className="w-4 h-4" /> : step}
          </div>
          {step < totalSteps && (
            <div className={`w-12 h-0.5 mx-2 ${
              step < currentStep ? 'bg-green-500' : 'bg-gray-200'
            }`} />
          )}
        </div>
      ))}
    </div>
  );

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-4">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                What are your child's interests?
              </h3>
              <p className="text-sm text-gray-600">
                Select all that apply to help us personalize their learning experience
              </p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-h-96 overflow-y-auto">
              {INTEREST_OPTIONS.map(interest => (
                <button
                  key={interest}
                  type="button"
                  onClick={() => handleInterestToggle(interest)}
                  className={`p-3 rounded-lg border-2 text-left transition-all ${
                    selectedInterests.includes(interest)
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <span className="text-sm font-medium">{interest}</span>
                </button>
              ))}
            </div>
            {selectedInterests.includes('Other') && (
              <div className="mt-4">
                <input
                  type="text"
                  value={otherInterest}
                  onChange={(e) => setOtherInterest(e.target.value)}
                  placeholder="Please specify your child's interest"
                  className="w-full p-3 border-2 border-gray-200 rounded-lg focus:border-blue-500 focus:ring-0"
                />
              </div>
            )}
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Preferred Learning Format
              </h3>
              <p className="text-sm text-gray-600">
                How does your child prefer to learn?
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {FORMAT_OPTIONS.map(format => (
                <button
                  key={format.value}
                  type="button"
                  onClick={() => handleFormatSelect(format.value)}
                  className={`p-4 rounded-lg border-2 text-center transition-all ${
                    preferredFormat === format.value
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <div className="text-2xl mb-2">{format.icon}</div>
                  <span className="text-sm font-medium">{format.value}</span>
                </button>
              ))}
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Preferred Session Length
              </h3>
              <p className="text-sm text-gray-600">
                How long should learning sessions typically be?
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {SESSION_LENGTH_OPTIONS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSessionLengthSelect(option.value)}
                  className={`p-4 rounded-lg border-2 text-center transition-all ${
                    preferredSessionLength === option.value
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <span className="text-lg font-semibold">{option.label}</span>
                </button>
              ))}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="text-blue-600 text-center">Learning Profile</CardTitle>
        <p className="text-sm text-gray-600 text-center">
          Help us personalize your child's learning experience
        </p>
      </CardHeader>
      <CardContent>
        {renderStepIndicator()}
        <div className="min-h-[400px]">
          {renderStepContent()}
        </div>

        <div className="flex justify-between items-center mt-8">
          <div>
            {currentStep > 1 && (
              <Button
                type="button"
                variant="outline"
                onClick={handlePrevious}
                className="flex items-center gap-2"
              >
                <ChevronLeft className="w-4 h-4" />
                Previous
              </Button>
            )}
          </div>

          <div className="flex gap-3">
            {onSkip && currentStep === 1 && (
              <Button
                type="button"
                variant="outline"
                onClick={onSkip}
                className="border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Skip for Now
              </Button>
            )}

            {currentStep < totalSteps ? (
              <Button
                type="button"
                onClick={handleNext}
                disabled={!canProceedToNext()}
                className="bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-2 disabled:opacity-50"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button
                type="button"
                onClick={handleSubmit}
                className="bg-green-600 hover:bg-green-700 text-white"
              >
                Save Profile
              </Button>
            )}
          </div>
        </div>

        {onSkip && currentStep === 1 && (
          <p className="text-xs text-gray-500 text-center mt-4">
            Note: You can complete this later, but it helps us provide better recommendations.
          </p>
        )}
      </CardContent>
    </Card>
  );
};

export default LearningProfileForm;