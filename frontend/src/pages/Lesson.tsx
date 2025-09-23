import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Play, CheckCircle, Circle, Brain, Network, Share2 } from 'lucide-react';

interface LessonSection {
  id: string;
  title: string;
  type: 'video' | 'content' | 'quiz';
  completed: boolean;
  content?: string;
  videoUrl?: string;
  quiz?: {
    question: string;
    options?: string[];
    correctAnswer?: string;
  };
}

interface LessonData {
  id: string;
  title: string;
  subject: string;
  progress: number;
  sections: LessonSection[];
  keyComponents?: {
    title: string;
    items: Array<{
      icon: React.ComponentType<any>;
      name: string;
      description: string;
    }>;
  };
}

export const Lesson: React.FC = () => {
  const { lessonId } = useParams();
  const navigate = useNavigate();
  const [currentSection, setCurrentSection] = useState(0);
  const [quizAnswer, setQuizAnswer] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [isVideoPlaying, setIsVideoPlaying] = useState(false);

  // Mock lesson data - in real app, this would come from API
  const [lessonData] = useState<LessonData>({
    id: lessonId || '1',
    title: 'AI Basics: Introduction to Neural Networks',
    subject: 'AI Basics',
    progress: 25,
    sections: [
      {
        id: '1',
        title: 'What are Neural Networks?',
        type: 'video',
        completed: true,
        content: 'Neural networks are computational models inspired by the structure and function of the human brain. They consist of interconnected nodes, or neurons, organized in layers. These networks learn by adjusting the connections between neurons based on the data they process.',
        videoUrl: 'https://example.com/neural-networks-intro.mp4'
      },
      {
        id: '2',
        title: 'Key Components',
        type: 'content',
        completed: false,
        content: 'Layers are the building blocks of neural networks, consisting of input, hidden, and output layers. Nodes, or neurons, are the processing units within each layer. Connections, also known as weights, determine the strength of the relationships between nodes.'
      },
      {
        id: '3',
        title: 'Quiz',
        type: 'quiz',
        completed: false,
        quiz: {
          question: 'What is the basic unit of a neural network?',
          options: ['Layer', 'Node/Neuron', 'Connection', 'Weight'],
          correctAnswer: 'Node/Neuron'
        }
      }
    ],
    keyComponents: {
      title: 'Key Components',
      items: [
        {
          icon: Network,
          name: 'Layers',
          description: 'Building blocks of neural networks'
        },
        {
          icon: Circle,
          name: 'Nodes',
          description: 'Processing units within each layer'
        },
        {
          icon: Share2,
          name: 'Connections',
          description: 'Relationships between nodes'
        }
      ]
    }
  });

  const currentSectionData = lessonData.sections[currentSection];

  const handleQuizSubmit = () => {
    setShowFeedback(true);
    // Mark section as completed if correct
    if (quizAnswer === currentSectionData.quiz?.correctAnswer) {
      lessonData.sections[currentSection].completed = true;
    }
  };

  const handleNext = () => {
    if (currentSection < lessonData.sections.length - 1) {
      setCurrentSection(currentSection + 1);
      setQuizAnswer('');
      setShowFeedback(false);
    } else {
      // Navigate to next lesson or back to dashboard
      navigate('/dashboard');
    }
  };

  const handlePrevious = () => {
    if (currentSection > 0) {
      setCurrentSection(currentSection - 1);
      setQuizAnswer('');
      setShowFeedback(false);
    }
  };

  const renderVideoSection = () => (
    <div className="space-y-6">
      <div className="relative bg-gradient-to-br from-teal-600 to-teal-800 rounded-2xl overflow-hidden aspect-video">
        <div className="absolute inset-0 flex items-center justify-center">
          {/* Animated background pattern */}
          <div className="absolute inset-0 opacity-20">
            <div className="absolute inset-0 bg-gradient-radial from-white/30 via-transparent to-transparent"></div>
            {[...Array(20)].map((_, i) => (
              <div
                key={i}
                className="absolute w-px bg-white/20"
                style={{
                  left: '50%',
                  top: '50%',
                  height: '200px',
                  transformOrigin: 'top',
                  transform: `rotate(${i * 18}deg) translateY(-100px)`,
                }}
              />
            ))}
          </div>
          
          {/* Play button */}
          <button
            onClick={() => setIsVideoPlaying(!isVideoPlaying)}
            className="relative z-10 w-20 h-20 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center hover:bg-white/30 transition-all duration-300 group"
          >
            <Play className="w-8 h-8 text-white ml-1 group-hover:scale-110 transition-transform" />
          </button>
        </div>
      </div>
      
      <div className="prose prose-gray max-w-none">
        <p className="text-gray-600 leading-relaxed">
          {currentSectionData.content}
        </p>
      </div>
    </div>
  );

  const renderContentSection = () => (
    <div className="space-y-8">
      {lessonData.keyComponents && (
        <div>
          <h3 className="text-xl font-semibold text-gray-900 mb-6 flex items-center">
            <Brain className="w-6 h-6 text-blue-600 mr-2" />
            {lessonData.keyComponents.title}
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {lessonData.keyComponents.items.map((item, index) => (
              <div key={index} className="text-center">
                <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <item.icon className="w-8 h-8 text-blue-600" />
                </div>
                <h4 className="font-semibold text-gray-900 mb-2">{item.name}</h4>
                <p className="text-sm text-gray-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      
      <div className="prose prose-gray max-w-none">
        <p className="text-gray-600 leading-relaxed">
          {currentSectionData.content}
        </p>
      </div>
    </div>
  );

  const renderQuizSection = () => (
    <div className="space-y-6">
      <div className="bg-blue-50 rounded-2xl p-8">
        <h3 className="text-xl font-semibold text-gray-900 mb-6 flex items-center">
          <CheckCircle className="w-6 h-6 text-blue-600 mr-2" />
          Quiz
        </h3>
        
        <div className="space-y-6">
          <p className="text-lg text-gray-800 font-medium">
            {currentSectionData.quiz?.question}
          </p>
          
          {currentSectionData.quiz?.options ? (
            <div className="space-y-3">
              {currentSectionData.quiz.options.map((option, index) => (
                <label
                  key={index}
                  className={`flex items-center p-4 rounded-xl border-2 cursor-pointer transition-all ${
                    quizAnswer === option
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="quiz-answer"
                    value={option}
                    checked={quizAnswer === option}
                    onChange={(e) => setQuizAnswer(e.target.value)}
                    className="sr-only"
                  />
                  <div className={`w-5 h-5 rounded-full border-2 mr-3 flex items-center justify-center ${
                    quizAnswer === option ? 'border-blue-500' : 'border-gray-300'
                  }`}>
                    {quizAnswer === option && (
                      <div className="w-2.5 h-2.5 bg-blue-500 rounded-full"></div>
                    )}
                  </div>
                  <span className="text-gray-700">{option}</span>
                </label>
              ))}
            </div>
          ) : (
            <textarea
              value={quizAnswer}
              onChange={(e) => setQuizAnswer(e.target.value)}
              placeholder="Your answer here..."
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all resize-none"
              rows={4}
            />
          )}
          
          {!showFeedback && (
            <button
              onClick={handleQuizSubmit}
              disabled={!quizAnswer.trim()}
              className="bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-3 rounded-xl font-medium transition-colors"
            >
              Submit
            </button>
          )}
          
          {showFeedback && (
            <div className={`p-4 rounded-xl ${
              quizAnswer === currentSectionData.quiz?.correctAnswer
                ? 'bg-green-50 border border-green-200'
                : 'bg-red-50 border border-red-200'
            }`}>
              <p className={`font-medium ${
                quizAnswer === currentSectionData.quiz?.correctAnswer
                  ? 'text-green-800'
                  : 'text-red-800'
              }`}>
                {quizAnswer === currentSectionData.quiz?.correctAnswer
                  ? 'Correct! Well done.'
                  : `Incorrect. The correct answer is: ${currentSectionData.quiz?.correctAnswer}`
                }
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb */}
        <nav className="flex items-center space-x-2 text-sm text-gray-600 mb-8">
          <button
            onClick={() => navigate('/dashboard')}
            className="hover:text-blue-600 transition-colors"
          >
            Lessons
          </button>
          <span>/</span>
          <span className="text-gray-900">{lessonData.subject}</span>
        </nav>

        {/* Lesson Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">
            {lessonData.title}
          </h1>
          
          {/* Progress Bar */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-700">Lesson Progress</span>
              <span className="text-sm font-medium text-blue-600">{lessonData.progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${lessonData.progress}%` }}
              ></div>
            </div>
          </div>
        </div>

        {/* Section Header */}
        <div className="mb-8">
          <h2 className="text-2xl font-semibold text-gray-900 flex items-center">
            <span className="w-8 h-8 bg-blue-600 text-white rounded-lg flex items-center justify-center text-sm font-bold mr-3">
              {currentSection + 1}
            </span>
            {currentSectionData.title}
          </h2>
        </div>

        {/* Section Content */}
        <div className="mb-12">
          {currentSectionData.type === 'video' && renderVideoSection()}
          {currentSectionData.type === 'content' && renderContentSection()}
          {currentSectionData.type === 'quiz' && renderQuizSection()}
        </div>

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <button
            onClick={handlePrevious}
            disabled={currentSection === 0}
            className="flex items-center px-6 py-3 bg-gray-200 text-gray-700 rounded-xl font-medium hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Previous
          </button>

          <div className="flex space-x-2">
            {lessonData.sections.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentSection(index)}
                className={`w-3 h-3 rounded-full transition-colors ${
                  index === currentSection
                    ? 'bg-blue-600'
                    : index < currentSection
                    ? 'bg-green-500'
                    : 'bg-gray-300'
                }`}
              />
            ))}
          </div>

          <button
            onClick={handleNext}
            className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors"
          >
            {currentSection === lessonData.sections.length - 1 ? 'Complete Lesson' : 'Next Lesson'}
            <ArrowRight className="w-4 h-4 ml-2" />
          </button>
        </div>
      </div>
    </div>
  );
};