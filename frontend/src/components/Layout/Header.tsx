import React, { useState } from 'react';
import { Menu, X, User, Bell, BookOpen, Home, TrendingUp, MessageCircle, Sparkles, Settings, CreditCard, Users } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

interface HeaderProps {
  variant?: 'landing' | 'dashboard';
}

export const Header: React.FC<HeaderProps> = ({ variant = 'landing' }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
const { user, signOut } = useAuth();

  // Decide navItems based on role
  const navItems =
    variant === 'dashboard' && user?.role === 'student'
      ? [
          { name: 'Home', path: '/child-dashboard', icon: Home },
          { name: 'Study Plan', path: '/study-plan', icon: BookOpen },
          { name: 'Progress', path: '/progress', icon: TrendingUp },
          { name: 'AI Tutor', path: '/ai-tutor', icon: MessageCircle },
        ]
      : variant === 'dashboard' && user?.role === 'parent'
      ? []
      : [
          { name: 'Home', path: '/', icon: Home },
          { name: 'About Us', path: '/about', icon: Sparkles },
          { name: 'Contact', path: '/contact', icon: MessageCircle },
        ];

  // Parent dropdown menu items
  const parentDropdownItems = [
    { name: 'Parent Settings', path: '/parent-settings', icon: Settings },

  ];

  const isActive = (path: string) => window.location.pathname === path;

  return (
    <header className="bg-gradient-to-r from-blue-600 via-purple-600 to-blue-600 shadow-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <a href="/" className="flex items-center space-x-3 group">
            <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-md transform group-hover:scale-110 transition-transform duration-200">
              <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-purple-500 rounded-lg flex items-center justify-center">
                <BookOpen className="w-4 h-4 text-white" />
              </div>
            </div>
            <div>
              <span className="text-xl font-bold text-white">Kaihle</span>
              <div className="text-xs text-blue-100 -mt-1">Learn. Grow. Succeed.</div>
            </div>
          </a>
          {/* Desktop Navigation */}
          {user?.role === 'student' && variant === 'dashboard' && (
            <nav className="hidden md:flex items-center space-x-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.path);
                return (
                  <a
                    key={item.name}
                    href={item.path}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-200 ${
                      active
                        ? 'bg-white text-blue-600 shadow-md'
                        : 'text-white hover:bg-white/20 backdrop-blur-sm'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-sm">{item.name}</span>
                  </a>
                );
              })}
            </nav>
          )}

          {/* Landing Navigation */}
          {variant === 'landing' && (
            <nav className="hidden md:flex items-center space-x-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <a
                    key={item.name}
                    href={item.path}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-white hover:bg-white/20 backdrop-blur-sm transition-all duration-200"
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-sm">{item.name}</span>
                  </a>
                );
              })}
            </nav>
          )}

          {/* Desktop Auth / Profile */}
          <div className="hidden md:flex items-center space-x-3">

            {user ? (
              <div className="flex items-center space-x-3">
                {/* Notifications only for students */}
                {user.role === 'student' && (
                  <button className="relative p-2 rounded-lg bg-white/20 backdrop-blur-sm hover:bg-white/30 transition-all duration-200">
                    <Bell className="w-5 h-5 text-white" />
                    <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                  </button>
                )}
                <div className="flex items-center gap-3 bg-white/20 backdrop-blur-sm rounded-lg px-4 py-2 hover:bg-white/30 transition-all duration-200 relative">
                  <div className="w-8 h-8 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center shadow-md">
                    <User className="w-4 h-4 text-white" />
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-semibold text-white">{user.full_name || 'Parent'}</div>
                    {user.role === 'student' && (
                      <div className="text-xs text-blue-100">{'Grade ' + (user.student_profile?.grade_level)}</div>
                    )}
                  </div>
                  {/* Dropdown menu button for parents */}
                  {user.role === 'parent' && (
                    <button
                      onClick={() => setIsMenuOpen(!isMenuOpen)}
                      className="p-1 rounded-lg bg-white/20 backdrop-blur-sm hover:bg-white/30 transition-all duration-200"
                    >
                      <Menu className="w-4 h-4 text-white" />
                    </button>
                  )}
                  {/* Parent dropdown menu */}
                  {user.role === 'parent' && isMenuOpen && (
                    <div className="absolute top-full right-0 mt-2 w-48 bg-white rounded-lg shadow-lg py-2 z-50">
                      {parentDropdownItems.map((item) => {
                        const Icon = item.icon;
                        const active = isActive(item.path);
                        return (
                          <a
                            key={item.name}
                            href={item.path}
                            onClick={() => setIsMenuOpen(false)}
                            className={`flex items-center gap-3 px-4 py-2 text-sm font-medium transition-all hover:bg-blue-50 ${active ? 'text-blue-600' : 'text-gray-700'}`}
                          >
                            <Icon className="w-4 h-4" />
                            <span>{item.name}</span>
                          </a>
                        );
                      })}
                    </div>
                  )}
                </div>
                <button
                  onClick={signOut}
                  className="px-4 py-2 rounded-lg font-medium text-white bg-white/20 backdrop-blur-sm hover:bg-white/30 transition-all duration-200"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <a
                  href="/student-login"
                  className="px-4 py-2 rounded-lg font-medium text-white hover:bg-white/20 backdrop-blur-sm transition-all duration-200"
                >
                  Student Login
                </a>
                <a
                  href="/parent-login"
                  className="px-4 py-2 rounded-lg font-medium text-white hover:bg-white/20 backdrop-blur-sm transition-all duration-200"
                >
                  Parent Login
                </a>
                <a
                  href="/signup"
                  className="px-5 py-2 rounded-lg font-semibold bg-white text-blue-600 hover:bg-blue-50 transition-all duration-200 shadow-lg"
                >
                  Sign Up Free
                </a>
              </div>
            )}
          </div>

          {/* Mobile Menu Button - only show for students */}
          {user?.role === 'student' && (
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="md:hidden p-2 rounded-lg bg-white/20 backdrop-blur-sm hover:bg-white/30 transition-all"
            >
              {isMenuOpen ? (
                <X className="w-6 h-6 text-white" />
              ) : (
                <Menu className="w-6 h-6 text-white" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Mobile Menu */}
  {isMenuOpen && (
    <div className="md:hidden bg-white/10 backdrop-blur-lg border-t border-white/20">
      <div className="px-4 py-4 space-y-2">
        {/* Show nav only if student */}
        {user?.role === 'student' &&
          navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            return (
              <a
                key={item.name}
                href={item.path}
                onClick={() => setIsMenuOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-all ${
                  active
                    ? 'bg-white text-blue-600 shadow-md'
                    : 'text-white hover:bg-white/20'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{item.name}</span>
              </a>
            );
          })}
        {/* Show parent dropdown items in mobile menu */}
        {user?.role === 'parent' &&
          parentDropdownItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            return (
              <a
                key={item.name}
                href={item.path}
                onClick={() => setIsMenuOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-all ${
                  active
                    ? 'bg-white text-blue-600 shadow-md'
                    : 'text-white hover:bg-white/20'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{item.name}</span>
              </a>
            );
          })}

            {/* Landing nav items */}
            {variant === 'landing' &&
              navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <a
                    key={item.name}
                    href={item.path}
                    onClick={() => setIsMenuOpen(false)}
                    className="flex items-center gap-3 px-4 py-3 rounded-lg font-medium text-white hover:bg-white/20 transition-all"
                  >
                    <Icon className="w-5 h-5" />
                    <span>{item.name}</span>
                  </a>
                );
              })}

            {user ? (
              <div className="pt-2 border-t border-white/20 space-y-2">
                <div className="flex items-center gap-3 px-4 py-3 bg-white/20 rounded-lg">
                  <div className="w-10 h-10 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center">
                    <User className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <div className="font-semibold text-white">{user.name || 'Student'}</div>
                    <div className="text-sm text-blue-100">Grade 6</div>
                  </div>
                </div>
                <button
                  onClick={() => {
                    signOut();
                    setIsMenuOpen(false);
                  }}
                  className="w-full px-4 py-3 rounded-lg font-medium bg-white/20 text-white hover:bg-white/30 transition-all"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <div className="pt-2 border-t border-white/20 space-y-2">
                <a
                  href="/student-login"
                  onClick={() => setIsMenuOpen(false)}
                  className="block w-full text-center px-4 py-3 rounded-lg font-medium text-white bg-white/20 hover:bg-white/30 transition-all"
                >
                  Student Login
                </a>
                <a
                  href="/parent-login"
                  onClick={() => setIsMenuOpen(false)}
                  className="block w-full text-center px-4 py-3 rounded-lg font-medium text-white bg-white/20 hover:bg-white/30 transition-all"
                >
                  Parent Login
                </a>
                <a
                  href="/signup"
                  onClick={() => setIsMenuOpen(false)}
                  className="block w-full text-center bg-white text-blue-600 hover:bg-blue-50 px-4 py-3 rounded-lg font-semibold transition-all shadow-lg"
                >
                  Sign Up Free
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
