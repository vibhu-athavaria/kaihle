import React from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Users, Trophy, Shield } from 'lucide-react';

export const Home: React.FC = () => {
  const features = [
    {
      icon: BookOpen,
      title: 'Personalized Paths',
      description: 'AI-driven paths adapt to each child\'s learning style and pace, ensuring optimal progress.',
    },
    {
      icon: Users,
      title: 'Collaboration Hub',
      description: 'Facilitate seamless communication between parents and teachers for collaborative student support.',
    },
    {
      icon: Trophy,
      title: 'Gamified Learning',
      description: 'Engaging elements like rewards and challenges motivate students and make learning enjoyable.',
    },
    {
      icon: Shield,
      title: 'Safe & Secure',
      description: 'Our platform prioritizes safety, providing a protected and monitored learning environment.',
    },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-blue-50 via-white to-cyan-50 pt-16 pb-24">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-100/20 to-cyan-100/20"></div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20">
          <div className="text-center">
            <h1 className="text-4xl md:text-6xl font-bold text-gray-900 mb-6">
              Unlock Your Child's Potential
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500">
                with AI-Powered Learning
              </span>
            </h1>

            <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto leading-relaxed">
              Future School offers personalized learning experiences for children aged 10-18,
              making education fun and effective. Our gamified approach keeps students
              engaged while providing valuable insights to parents and teachers.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                to="/signup"
                className="bg-blue-600 text-white hover:bg-blue-700 px-8 py-4 rounded-xl text-lg font-semibold transition-all duration-200 transform hover:scale-105 shadow-lg hover:shadow-xl"
              >
                Get Started Free
              </Link>
              <Link
                to="/demo"
                className="bg-white text-gray-700 hover:bg-blue-50 border-2 border-gray-300 hover:border-blue-300 px-8 py-4 rounded-xl text-lg font-semibold transition-all duration-200 shadow-md hover:shadow-lg"
              >
                Request a Demo
              </Link>
            </div>
          </div>
        </div>

        {/* Decorative Elements */}
        <div className="absolute top-20 left-10 w-20 h-20 bg-blue-200 rounded-full opacity-20"></div>
        <div className="absolute top-40 right-20 w-32 h-32 bg-cyan-200 rounded-full opacity-20"></div>
        <div className="absolute bottom-20 left-1/4 w-16 h-16 bg-blue-300 rounded-full opacity-20"></div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-blue-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
              Everything You Need for a Brighter Future
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Future School provides a comprehensive learning platform with features designed to
              enhance the educational journey for students, parents, and educators.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div
                key={index}
                className="bg-white rounded-2xl p-8 shadow-md hover:shadow-lg transition-all duration-300 transform hover:-translate-y-2 group"
              >
                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-6 group-hover:bg-blue-200 transition-colors">
                  <feature.icon className="w-8 h-8 text-blue-600" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-4">
                  {feature.title}
                </h3>
                <p className="text-gray-600 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};