import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Check, X, ArrowRight, CreditCard, Clock, Users, BookOpen, BarChart2 } from 'lucide-react';

export const Pricing: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [selectedPlan, setSelectedPlan] = useState<'basic' | 'standard' | 'premium'>('standard');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');

  const pricingOptions = {
    basic: {
      name: 'Basic',
      description: 'Perfect for one student and one subject',
      price: billingCycle === 'monthly' ? 25 : 22.50,
      students: 1,
      subjects: 1,
      features: [
        '1 student profile',
        '1 subject access',
        'Basic progress tracking',
        'Standard assessments',
        'Email support'
      ],
      popular: false
    },
    standard: {
      name: 'Standard',
      description: 'Great for one student with multiple subjects',
      price: billingCycle === 'monthly' ? 75 : 67.50,
      students: 1,
      subjects: 3,
      features: [
        '1 student profile',
        '3 subjects access',
        'Advanced progress tracking',
        'Personalized learning paths',
        'Priority email support',
        'Assessment analytics'
      ],
      popular: true
    },
    premium: {
      name: 'Premium',
      description: 'Best value for families with multiple children',
      price: billingCycle === 'monthly' ? 150 : 135,
      students: 2,
      subjects: 'Unlimited',
      features: [
        '2 student profiles',
        'Unlimited subjects',
        'Full progress tracking',
        'AI-powered learning paths',
        '24/7 priority support',
        'Detailed assessment reports',
        'Parent coaching sessions'
      ],
      popular: false
    }
  };

  const handleGetStarted = () => {
    if (!user) {
      navigate('/signup');
    } else {
      navigate('/parent-settings?tab=billing');
    }
  };

  const handleStartFreeTrial = () => {
    if (!user) {
      navigate('/signup');
    } else {
      navigate('/parent-settings?tab=billing');
    }
  };

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">Simple, Transparent Pricing</h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            No hidden fees. No surprises. Just great learning at an affordable price.
          </p>
        </div>

        {/* Free Trial Banner */}
        <div className="mb-12">
          <div className="bg-yellow-50 border-2 border-yellow-200 rounded-2xl p-8 text-center">
            <div className="flex items-center justify-center mb-4">
              <span className="bg-yellow-600 text-white px-3 py-1 rounded-full text-sm font-medium mr-3">
                15 DAYS FREE
              </span>
              <h3 className="text-2xl font-bold text-gray-900">Start with a 15-day free trial</h3>
            </div>
            <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
              Experience the full power of Kaihle with no commitment. Cancel anytime.
            </p>
            <button
              onClick={handleStartFreeTrial}
              className="bg-yellow-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:bg-yellow-700 transition-colors transform hover:scale-105"
            >
              Start Free Trial
            </button>
          </div>
        </div>

        {/* Billing Cycle Toggle */}
        <div className="flex justify-center mb-8">
          <div className="bg-white rounded-xl p-1 shadow-sm">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`px-6 py-2 rounded-lg font-medium transition-colors ${billingCycle === 'monthly' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              Monthly Billing
            </button>
            <button
              onClick={() => setBillingCycle('annual')}
              className={`px-6 py-2 rounded-lg font-medium transition-colors ${billingCycle === 'annual' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              Annual Billing (10% off)
            </button>
          </div>
        </div>

        {/* Pricing Plans */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
          {/* Basic Plan */}
          <div className={`bg-white rounded-2xl shadow-lg p-8 flex flex-col ${pricingOptions.basic.popular ? 'ring-2 ring-blue-600' : ''}`}>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">{pricingOptions.basic.name}</h3>
            <p className="text-gray-600 mb-6">{pricingOptions.basic.description}</p>

            <div className="mb-6">
              <span className="text-5xl font-bold text-gray-900">${pricingOptions.basic.price}</span>
              <span className="text-gray-500">/month</span>
              {billingCycle === 'annual' && (
                <p className="text-sm text-gray-500 mt-1">Billed annually at ${pricingOptions.basic.price * 12 * 0.90}/year</p>
              )}
            </div>

            <div className="mb-8">
              <p className="text-sm text-gray-500 mb-2">Includes:</p>
              <ul className="space-y-3">
                {pricingOptions.basic.features.map((feature, index) => (
                  <li key={index} className="flex items-center">
                    <Check className="w-5 h-5 text-green-500 mr-3" />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>

            <button
              onClick={() => {
                setSelectedPlan('basic');
                handleGetStarted();
              }}
              className={`w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors ${selectedPlan === 'basic' ? 'ring-2 ring-blue-300' : ''}`}
            >
              {user ? 'Choose Plan' : 'Get Started'}
            </button>
          </div>

          {/* Standard Plan (Popular) */}
          <div className={`bg-white rounded-2xl shadow-lg p-8 flex flex-col ring-2 ring-blue-600 relative`}>
            <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
              <span className="bg-blue-600 text-white px-4 py-1 rounded-full text-sm font-medium">
                MOST POPULAR
              </span>
            </div>

            <h3 className="text-2xl font-bold text-gray-900 mb-2 mt-4">{pricingOptions.standard.name}</h3>
            <p className="text-gray-600 mb-6">{pricingOptions.standard.description}</p>

            <div className="mb-6">
              <span className="text-5xl font-bold text-gray-900">${pricingOptions.standard.price}</span>
              <span className="text-gray-500">/month</span>
              {billingCycle === 'annual' && (
                <p className="text-sm text-gray-500 mt-1">Billed annually at ${pricingOptions.standard.price * 12 * 0.90}/year</p>
              )}
            </div>

            <div className="mb-8">
              <p className="text-sm text-gray-500 mb-2">Includes:</p>
              <ul className="space-y-3">
                {pricingOptions.standard.features.map((feature, index) => (
                  <li key={index} className="flex items-center">
                    <Check className="w-5 h-5 text-green-500 mr-3" />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>

            <button
              onClick={() => {
                setSelectedPlan('standard');
                handleGetStarted();
              }}
              className={`w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors ${selectedPlan === 'standard' ? 'ring-2 ring-blue-300' : ''}`}
            >
              {user ? 'Choose Plan' : 'Get Started'}
            </button>
          </div>

          {/* Premium Plan */}
          <div className={`bg-white rounded-2xl shadow-lg p-8 flex flex-col ${pricingOptions.premium.popular ? 'ring-2 ring-blue-600' : ''}`}>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">{pricingOptions.premium.name}</h3>
            <p className="text-gray-600 mb-6">{pricingOptions.premium.description}</p>

            <div className="mb-6">
              <span className="text-5xl font-bold text-gray-900">${pricingOptions.premium.price}</span>
              <span className="text-gray-500">/month</span>
              {billingCycle === 'annual' && (
                <p className="text-sm text-gray-500 mt-1">Billed annually at ${pricingOptions.premium.price * 12 * 0.90}/year</p>
              )}
            </div>

            <div className="mb-8">
              <p className="text-sm text-gray-500 mb-2">Includes:</p>
              <ul className="space-y-3">
                {pricingOptions.premium.features.map((feature, index) => (
                  <li key={index} className="flex items-center">
                    <Check className="w-5 h-5 text-green-500 mr-3" />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>
            </div>

            <button
              onClick={() => {
                setSelectedPlan('premium');
                handleGetStarted();
              }}
              className={`w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors ${selectedPlan === 'premium' ? 'ring-2 ring-blue-300' : ''}`}
            >
              {user ? 'Choose Plan' : 'Get Started'}
            </button>
          </div>
        </div>

        {/* Pricing Details */}
        <div className="bg-white rounded-2xl shadow-sm p-8 mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-6 text-center">Simple, Fair Pricing</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="flex items-start">
              <div className="flex-shrink-0 mr-4">
                <CreditCard className="w-8 h-8 text-blue-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">Pay Per Student, Per Subject</h4>
                <p className="text-gray-600">Only pay for what you need. $25 per student per subject per month gives you full access to our comprehensive learning platform.</p>
              </div>
            </div>

            <div className="flex items-start">
              <div className="flex-shrink-0 mr-4">
                <Clock className="w-8 h-8 text-blue-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">No Long-Term Contracts</h4>
                <p className="text-gray-600">Cancel anytime with no penalties. Your subscription renews monthly unless you cancel.</p>
              </div>
            </div>

            <div className="flex items-start">
              <div className="flex-shrink-0 mr-4">
                <Users className="w-8 h-8 text-blue-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">Family Discounts</h4>
                <p className="text-gray-600">Add multiple children and subjects to get volume discounts. Contact us for custom family plans.</p>
              </div>
            </div>

            <div className="flex items-start">
              <div className="flex-shrink-0 mr-4">
                <BookOpen className="w-8 h-8 text-blue-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">All Subjects Included</h4>
                <p className="text-gray-600">Access our full curriculum including Mathematics, Science, English, and Humanities with any subscription.</p>
              </div>
            </div>
          </div>
        </div>

        {/* What's Included */}
        <div className="bg-white rounded-2xl shadow-sm p-8 mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-8 text-center">Everything You Need for Learning Success</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <BarChart2 className="w-8 h-8 text-blue-600" />
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">Personalized Learning Paths</h4>
              <p className="text-gray-600 text-sm">AI-powered adaptive learning that adjusts to your child's unique needs and pace.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-blue-600" />
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">Comprehensive Assessments</h4>
              <p className="text-gray-600 text-sm">Regular diagnostic and formative assessments with detailed performance analytics.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Users className="w-8 h-8 text-blue-600" />
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">Parent Dashboard</h4>
              <p className="text-gray-600 text-sm">Real-time progress tracking, detailed reports, and actionable insights for parents.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CreditCard className="w-8 h-8 text-blue-600" />
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">AI Tutor Access</h4>
              <p className="text-gray-600 text-sm">24/7 access to our AI tutoring system for personalized help and explanations.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <BookOpen className="w-8 h-8 text-blue-600" />
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">Curriculum Alignment</h4>
              <p className="text-gray-600 text-sm">Fully aligned with CBSE, IB, IGCSE, and Common Core standards.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Clock className="w-8 h-8 text-blue-600" />
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">Progress Tracking</h4>
              <p className="text-gray-600 text-sm">Comprehensive progress tracking with badges, streaks, and achievement systems.</p>
            </div>
          </div>
        </div>

        {/* FAQ Section */}
        <div className="bg-white rounded-2xl shadow-sm p-8 mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-8 text-center">Frequently Asked Questions</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-semibold text-gray-900 mb-2">What happens after the free trial?</h4>
              <p className="text-gray-600 text-sm mb-4">After your 15-day free trial, your subscription will automatically continue with the selected plan. You can cancel anytime before the trial ends to avoid being charged.</p>
            </div>

            <div>
              <h4 className="font-semibold text-gray-900 mb-2">Can I change my plan later?</h4>
              <p className="text-gray-600 text-sm mb-4">Yes, you can upgrade or downgrade your plan at any time from your account settings. Changes will be prorated and applied to your next billing cycle.</p>
            </div>

            <div>
              <h4 className="font-semibold text-gray-900 mb-2">Do you offer discounts for schools or large families?</h4>
              <p className="text-gray-600 text-sm mb-4">Yes, we offer special pricing for schools and families with 3+ children. Please contact our sales team for custom quotes.</p>
            </div>

            <div>
              <h4 className="font-semibold text-gray-900 mb-2">What payment methods do you accept?</h4>
              <p className="text-gray-600 text-sm mb-4">We accept all major credit cards (Visa, Mastercard, American Express) and PayPal. Payment is processed securely through our PCI-compliant payment gateway.</p>
            </div>

            <div>
              <h4 className="font-semibold text-gray-900 mb-2">Can I get a refund?</h4>
              <p className="text-gray-600 text-sm mb-4">We offer a 30-day money-back guarantee. If you're not satisfied with Kaihle, contact us within 30 days for a full refund.</p>
            </div>

            <div>
              <h4 className="font-semibold text-gray-900 mb-2">Is there a contract or commitment?</h4>
              <p className="text-gray-600 text-sm mb-4">No, there are no contracts or long-term commitments. You can cancel your subscription at any time with no penalties.</p>
            </div>
          </div>
        </div>

        {/* Final CTA */}
        <div className="text-center">
          <h2 className="text-4xl font-bold text-gray-900 mb-4">Ready to Transform Your Child's Learning?</h2>
          <p className="text-xl text-gray-600 mb-8">Join thousands of parents who trust Kaihle for personalized, effective learning.</p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleStartFreeTrial}
              className="bg-yellow-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:bg-yellow-700 transition-colors transform hover:scale-105 flex items-center justify-center"
            >
              <span className="mr-2">Start Free Trial</span>
              <ArrowRight className="w-5 h-5" />
            </button>

            <button
              onClick={() => navigate(user ? '/parent-settings' : '/signup')}
              className="bg-blue-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:bg-blue-700 transition-colors transform hover:scale-105 flex items-center justify-center"
            >
              <span className="mr-2">{user ? 'Choose Your Plan' : 'Get Started'}</span>
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};