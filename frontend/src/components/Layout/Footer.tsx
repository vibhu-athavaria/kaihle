import React from 'react';
import { BookOpen, Mail, MapPin, Heart, Facebook, Twitter, Instagram, Linkedin } from 'lucide-react';

export const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white mt-auto">
      {/* Main Footer Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand Section */}
          <div className="col-span-1 md:col-span-2">
            <div className="flex items-center space-x-3 mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-xl flex items-center justify-center shadow-lg">
                <BookOpen className="w-6 h-6 text-white" />
              </div>
              <div>
                <span className="text-2xl font-bold text-white">Kaihle</span>
                <div className="text-sm text-blue-200">Personalized Learning for Every Child</div>
              </div>
            </div>
            <p className="text-gray-300 mb-6 max-w-md">
              Empowering students ages 7-14 with AI-powered personalized education.
              Build strong foundations and discover the joy of learning.
            </p>
            <div className="flex space-x-3">
              <a
                href="https://facebook.com"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 bg-white/10 backdrop-blur-sm rounded-lg flex items-center justify-center hover:bg-white/20 transition-all"
                aria-label="Facebook"
              >
                <Facebook className="w-5 h-5" />
              </a>
              <a
                href="https://twitter.com"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 bg-white/10 backdrop-blur-sm rounded-lg flex items-center justify-center hover:bg-white/20 transition-all"
                aria-label="Twitter"
              >
                <Twitter className="w-5 h-5" />
              </a>
              <a
                href="https://instagram.com"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 bg-white/10 backdrop-blur-sm rounded-lg flex items-center justify-center hover:bg-white/20 transition-all"
                aria-label="Instagram"
              >
                <Instagram className="w-5 h-5" />
              </a>
              <a
                href="https://linkedin.com"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 bg-white/10 backdrop-blur-sm rounded-lg flex items-center justify-center hover:bg-white/20 transition-all"
                aria-label="LinkedIn"
              >
                <Linkedin className="w-5 h-5" />
              </a>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-semibold text-lg mb-4 text-white">Quick Links</h3>
            <ul className="space-y-2">
              <li>
                <a href="/" className="text-gray-300 hover:text-white transition-colors">
                  Home
                </a>
              </li>
              <li>
                <a href="/about" className="text-gray-300 hover:text-white transition-colors">
                  About Us
                </a>
              </li>
              <li>
                <a href="/how-it-works" className="text-gray-300 hover:text-white transition-colors">
                  How It Works
                </a>
              </li>
              <li>
                <a href="/pricing" className="text-gray-300 hover:text-white transition-colors">
                  Pricing
                </a>
              </li>
              <li>
                <a href="/faq" className="text-gray-300 hover:text-white transition-colors">
                  FAQ
                </a>
              </li>
            </ul>
          </div>

          {/* Contact Info */}
          <div>
            <h3 className="font-semibold text-lg mb-4 text-white">Contact Us</h3>
            <ul className="space-y-3">
              <li className="flex items-start gap-3 text-gray-300">
                <Mail className="w-5 h-5 mt-0.5 text-blue-400 flex-shrink-0" />
                <div>
                  <div className="text-sm">Email</div>
                  <a href="mailto:hello@kaihle.com" className="hover:text-white transition-colors">
                    hello@kaihle.com
                  </a>
                </div>
              </li>
              <li className="flex items-start gap-3 text-gray-300">
                <MapPin className="w-5 h-5 mt-0.5 text-blue-400 flex-shrink-0" />
                <div>
                  <div className="text-sm">Location</div>
                  <span>San Francisco, CA</span>
                </div>
              </li>
            </ul>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-white/10 my-8"></div>

        {/* Bottom Section */}
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2 text-gray-300">
            <span>© {currentYear} Kaihle. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-1 text-gray-300">
            <span>Made with</span>
            <Heart className="w-4 h-4 text-red-500 fill-red-500" />
            <span>for students everywhere</span>
          </div>
          <div className="flex gap-6 text-sm">
            <a href="/privacy" className="text-gray-300 hover:text-white transition-colors">
              Privacy Policy
            </a>
            <a href="/terms" className="text-gray-300 hover:text-white transition-colors">
              Terms of Service
            </a>
          </div>
        </div>
      </div>

      {/* Decorative Elements */}
      <div className="relative h-2 bg-gradient-to-r from-blue-500 via-purple-500 to-blue-500"></div>
    </footer>
  );
};
