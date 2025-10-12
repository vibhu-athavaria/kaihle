import React from 'react';
import { Clock, BookOpen, Beaker, Scroll, Edit3 } from 'lucide-react';

interface StudyTask {
  id: string;
  subject: string;
  title: string;
  description: string;
  duration: number;
  icon: React.ComponentType<any>;
  color: string;
}

export const StudyPlan: React.FC = () => {
  const weeklyProgress = 60;

  const studyTasks: StudyTask[] = [
    {
      id: '1',
      subject: 'Math',
      title: 'Algebra Basics',
      description: 'Complete 3 exercises on linear equations.',
      duration: 15,
      icon: BookOpen,
      color: 'text-blue-600'
    },
    {
      id: '2',
      subject: 'Science',
      title: 'Biology Fundamentals',
      description: 'Watch a video on cell structure and take a quiz.',
      duration: 25,
      icon: Beaker,
      color: 'text-blue-600'
    },
    {
      id: '3',
      subject: 'History',
      title: 'World War II',
      description: 'Read chapter 5 and answer comprehension questions.',
      duration: 30,
      icon: Scroll,
      color: 'text-blue-600'
    },
    {
      id: '4',
      subject: 'English',
      title: 'Creative Writing',
      description: 'Write a short story about a futuristic city.',
      duration: 45,
      icon: Edit3,
      color: 'text-blue-600'
    }
  ];

  const handleStartTask = (taskId: string) => {
    // Navigate to lesson page
    window.location.href = `/lesson/${taskId}`;
  };

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Your Study Plan
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Personalized for your learning goals and ready for you to conquer.
          </p>
        </div>

        {/* Weekly Progress */}
        <div className="mb-12">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Weekly Progress</h2>
            <span className="text-2xl font-bold text-blue-600">{weeklyProgress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${weeklyProgress}%` }}
            ></div>
          </div>
        </div>

        {/* Study Tasks Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {studyTasks.map((task) => (
            <div
              key={task.id}
              className="bg-white rounded-2xl p-8 shadow-sm hover:shadow-md transition-all duration-200 group"
            >
              {/* Subject Label */}
              <div className="mb-4">
                <span className={`text-sm font-medium ${task.color} bg-blue-50 px-3 py-1 rounded-full`}>
                  {task.subject}
                </span>
              </div>

              {/* Task Title */}
              <h3 className="text-2xl font-bold text-gray-900 mb-3">
                {task.title}
              </h3>

              {/* Task Description */}
              <p className="text-gray-600 mb-6 leading-relaxed">
                {task.description}
              </p>

              {/* Duration and Start Button */}
              <div className="flex items-center justify-between">
                <div className="flex items-center text-gray-500">
                  <Clock className="w-4 h-4 mr-2" />
                  <span className="text-sm font-medium">{task.duration} min</span>
                </div>
                <button
                  onClick={() => handleStartTask(task.id)}
                  className="bg-blue-600 text-white hover:bg-blue-700 px-6 py-3 rounded-xl font-medium transition-all duration-200 transform hover:scale-105 shadow-md hover:shadow-lg"
                >
                  Start Task
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Additional Study Tips */}
        <div className="mt-16 bg-gradient-to-br from-blue-50 to-cyan-50 rounded-2xl p-8">
          <div className="text-center">
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              Study Tips for Success
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Clock className="w-8 h-8 text-blue-600" />
                </div>
                <h4 className="font-semibold text-gray-900 mb-2">Stay Consistent</h4>
                <p className="text-sm text-gray-600">
                  Complete your daily tasks to maintain momentum and build lasting habits.
                </p>
              </div>
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <BookOpen className="w-8 h-8 text-blue-600" />
                </div>
                <h4 className="font-semibold text-gray-900 mb-2">Take Notes</h4>
                <p className="text-sm text-gray-600">
                  Write down key concepts and ideas to reinforce your learning.
                </p>
              </div>
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Beaker className="w-8 h-8 text-blue-600" />
                </div>
                <h4 className="font-semibold text-gray-900 mb-2">Practice Regularly</h4>
                <p className="text-sm text-gray-600">
                  Apply what you learn through exercises and real-world examples.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};