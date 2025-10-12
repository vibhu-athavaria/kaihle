import React, { useState, useRef } from 'react';
import { Send, Paperclip, Camera, Sparkles } from 'lucide-react';

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
}

export const AITutor: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    // Simulate AI response
    setTimeout(() => {
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        content: `Great question about "${inputValue}"! Let me help you understand this concept better.

This is a simulated AI tutor response. In a real implementation, this would connect to OpenAI's API or Claude to provide intelligent, curriculum-specific answers to your questions.

Here's what I would explain:
1. Key concepts related to your question
2. Step-by-step explanations
3. Relevant examples and practice problems
4. Additional resources for further learning

Would you like me to dive deeper into any specific aspect?`,
        isUser: false,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, aiResponse]);
      setLoading(false);
    }, 2000);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFileUpload = () => {
    fileInputRef.current?.click();
  };

  const handleCameraCapture = () => {
    // Handle camera capture logic
    console.log('Camera capture requested');
  };

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-purple-600 rounded-2xl flex items-center justify-center">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">AI Tutor</h1>
          <p className="text-gray-600 max-w-2xl mx-auto">
            Ask me anything! I can explain concepts, provide resources, or even help you with your
            math homework.
          </p>
        </div>

        {/* Chat Container */}
        <div className="bg-white rounded-2xl shadow-lg h-[600px] flex flex-col">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 mt-20">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-6 h-6 text-blue-600" />
                </div>
                <p className="text-lg font-medium mb-2">Ready to help you learn!</p>
                <p className="text-sm">Ask any question to get started</p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl ${
                      message.isUser
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    <p
                      className={`text-xs mt-1 ${
                        message.isUser ? 'text-blue-100' : 'text-gray-500'
                      }`}
                    >
                      {message.timestamp.toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </p>
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 text-gray-900 max-w-xs lg:max-w-md px-4 py-3 rounded-2xl">
                  <div className="flex items-center space-x-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                    <span className="text-sm text-gray-500">AI Tutor is thinking...</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className="border-t border-gray-200 p-6">
            <div className="flex items-end space-x-4">
              <div className="flex-1">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your question here... e.g., 'Explain photosynthesis' or 'What is 2x + 5 = 15?'"
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all resize-none"
                  rows={3}
                />
              </div>
              <div className="flex flex-col space-y-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept="image/*,application/pdf,.doc,.docx"
                  onChange={() => console.log('File selected')}
                />
                <button
                  onClick={handleFileUpload}
                  className="p-3 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-colors"
                  title="Attach File"
                >
                  <Paperclip className="w-5 h-5" />
                </button>
                <button
                  onClick={handleCameraCapture}
                  className="p-3 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-colors"
                  title="Use Camera"
                >
                  <Camera className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="flex justify-end mt-4">
              <button
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || loading}
                className="bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-3 rounded-xl font-medium transition-colors flex items-center space-x-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>Ask AI Tutor</span>
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};