import React, { useEffect, useState } from 'react';
import { BookOpen, Beaker, Scroll, Edit3, Paintbrush, Music } from 'lucide-react';
import { Child, Lesson } from '../types';

const subjectIcons = {
  Math: BookOpen,
  Science: Beaker,
  History: Scroll,
  English: Edit3,
  Art: Paintbrush,
  Music: Music,
};

export const ChildDashboard: React.FC = () => {
  const [child, setChild] = useState<Child | null>(null);
  const [todaysTasks, setTodaysTasks] = useState<Lesson[]>([]);
  const [upcomingLessons, setUpcomingLessons] = useState<Lesson[]>([]);

  useEffect(() => {
    // Load child data
    const currentChild = localStorage.getItem('currentChild');
    if (currentChild) {
      try {
        setChild(JSON.parse(currentChild));
      } catch (error) {
        console.error('Error parsing child data:', error);
        // Create a default child if none exists
        const defaultChild: Child = {
          id: 'default-child',
          parent_id: 'current-user',
          full_name: 'Student',
          age: 12,
          grade: '7th Grade',
          created_at: new Date().toISOString(),
        };
        setChild(defaultChild);
        localStorage.setItem('currentChild', JSON.stringify(defaultChild));
      }
    } else {
      // Create a default child if none exists
      const defaultChild: Child = {
        id: 'default-child',
        parent_id: 'current-user',
        full_name: 'Student',
        age: 12,
        grade: '7th Grade',
        created_at: new Date().toISOString(),
      };
      setChild(defaultChild);
      localStorage.setItem('currentChild', JSON.stringify(defaultChild));
    }

    // Mock data for lessons
    setTodaysTasks([
      {
        id: '1',
        title: 'Algebra Basics',
        subject: 'Math',
        icon: 'BookOpen',
        type: 'today',
        child_id: '1'
      },
      {
        id: '2',
        title: 'The Solar System',
        subject: 'Science',
        icon: 'Beaker',
        type: 'today',
        child_id: '1'
      },
      {
        id: '3',
        title: 'Ancient Civilizations',
        subject: 'History',
        icon: 'Scroll',
        type: 'today',
        child_id: '1'
      }
    ]);

    setUpcomingLessons([
      {
        id: '4',
        title: 'Creative Writing',
        subject: 'English',
        icon: 'Edit3',
        type: 'upcoming',
        schedule: 'Tomorrow',
        child_id: '1'
      },
      {
        id: '5',
        title: 'Drawing Fundamentals',
        subject: 'Art',
        icon: 'Paintbrush',
        type: 'upcoming',
        schedule: 'In 2 days',
        child_id: '1'
      },
      {
        id: '6',
        title: 'Music Theory',
        subject: 'Music',
        icon: 'Music',
        type: 'upcoming',
        schedule: 'In 3 days',
        child_id: '1'
      }
    ]);
  }, []);

  const handleStartLesson = (lessonId: string) => {
    // Navigate to lesson page
    window.location.href = `/lesson/${lessonId}`;
  };

  if (!child) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Welcome back, {child.full_name}!
          </h1>
          <p className="text-gray-600 flex items-center">
            Let's continue your learning journey and crush those goals! ✨
          </p>
        </div>

        {/* Tabs */}
        <div className="mb-8">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <button className="border-b-2 border-blue-600 py-2 px-1 text-blue-600 font-medium text-sm">
                My Plan
              </button>
              <button className="border-transparent py-2 px-1 text-gray-500 hover:text-gray-700 font-medium text-sm">
                My Progress
              </button>
            </nav>
          </div>
        </div>

        {/* Today's Tasks */}
        <div className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Today's Tasks</h2>
          <div className="space-y-4">
            {todaysTasks.map((task) => {
              const IconComponent = subjectIcons[task.subject as keyof typeof subjectIcons] || BookOpen;
              return (
                <div
                  key={task.id}
                  className="bg-white rounded-xl p-6 shadow-sm hover:shadow-md transition-all duration-200 flex items-center justify-between group"
                >
                  <div className="flex items-center space-x-4">
                    <div className="w-16 h-16 bg-blue-100 rounded-xl flex items-center justify-center group-hover:bg-blue-200 transition-colors">
                      <IconComponent className="w-8 h-8 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-1">
                        {task.title}
                      </h3>
                      <p className="text-gray-600">{task.subject}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleStartLesson(task.id)}
                    className="bg-blue-600 text-white hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition-colors"
                  >
                    Start Lesson
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Upcoming Lessons */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Upcoming Lessons</h2>
          <div className="space-y-4">
            {upcomingLessons.map((lesson) => {
              const IconComponent = subjectIcons[lesson.subject as keyof typeof subjectIcons] || BookOpen;
              return (
                <div
                  key={lesson.id}
                  className="bg-white rounded-xl p-6 shadow-sm hover:shadow-md transition-all duration-200 flex items-center justify-between group"
                >
                  <div className="flex items-center space-x-4">
                    <div className="w-16 h-16 bg-gray-100 rounded-xl flex items-center justify-center group-hover:bg-gray-200 transition-colors">
                      <IconComponent className="w-8 h-8 text-gray-600" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-1">
                        {lesson.title}
                      </h3>
                      <p className="text-gray-600">{lesson.subject}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-gray-900">{lesson.schedule}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};