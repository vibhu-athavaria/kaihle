import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Check, X, ArrowRight, CreditCard, Clock, Users, BookOpen, BarChart2, AlertTriangle } from 'lucide-react';
import { getSubscriptionPlans } from '../services/billingService';
import { http } from '../lib/http';

export const Pricing: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [pricingData, setPricingData] = useState<PricingOptionsResponse | null>(null);
  const [billingSummary, setBillingSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<'basic' | 'premium'>('basic');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('annual');

  // Check if redirected due to trial expiration
  const urlParams = new URLSearchParams(window.location.search);
  const trialExpired = urlParams.get('reason') === 'trial_expired';

  // Fetch subscription plans and billing summary from backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        const plansPromise = getSubscriptionPlans();
        const summaryPromise = user ? http.get('/api/v1/billing/summary') : Promise.resolve(null);

        const [plans, summaryResponse] = await Promise.all([plansPromise, summaryPromise]);

        // Transform the data to match the expected format
        const transformedData = {
          pricing_options: plans.map(plan => ({
            plan_id: plan.id,
            name: plan.name,
            description: plan.description,
            plan_type: plan.plan_type,
            trial_days: plan.trial_days,
            monthly_price: plan.base_price,
            yearly_price: plan.yearly_price || plan.base_price * 12 * (1 - 0.20),
            currency: plan.currency,
            features: [] // Will be populated from plan features if available
          })),
          free_trial_days: plans[0]?.trial_days || 15,
          available_billing_cycles: ['monthly', 'yearly'],
          total_subjects_available: 4
        };
        setPricingData(transformedData);
        if (summaryResponse) {
          setBillingSummary(summaryResponse.data);
        }
      } catch (err) {
        console.error('Failed to fetch data:', err);
        setError('Failed to load pricing information. Using fallback data.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [user]);

  // Fallback to hardcoded data if API fails or while loading
  const getPricingOptionsData = () => {
    if (loading) {
      return {
        pricing_options: [
          {
            plan_id: 1,
            name: 'Basic',
            description: 'One subject per student',
            plan_type: 'basic',
            trial_days: 15,
            monthly_price: 25.00,
            yearly_price: 270.00,
            currency: 'USD',
            features: [
              { name: '1 student profile', description: 'Access for one student' },
              { name: '1 subject access', description: 'Choose one subject' },
              { name: 'Basic progress tracking', description: 'Track learning progress' },
              { name: 'Standard assessments', description: 'Regular assessments' },
              { name: 'Email support', description: 'Customer support via email' }
            ]
          },
          {
            plan_id: 2,
            name: 'Premium',
            description: 'All subjects (Science, Math, English, Humanities) per student',
            plan_type: 'premium',
            trial_days: 15,
            monthly_price: 80.00,
            yearly_price: 864.00,
            currency: 'USD',
            features: [
              { name: 'All subjects access', description: 'Access to all available subjects' },
              { name: 'Advanced progress tracking', description: 'Detailed progress analytics' },
              { name: 'Personalized learning paths', description: 'AI-powered learning paths' },
              { name: 'Priority support', description: '24/7 priority customer support' },
              { name: 'Detailed assessment reports', description: 'Comprehensive assessment analytics' },
              { name: 'Parent coaching sessions', description: 'Regular coaching sessions for parents' }
            ]
          }
        ],
        free_trial_days: 15,
        available_billing_cycles: ['monthly', 'yearly'],
        total_subjects_available: 4
      };
    }

    if (error || !pricingData) {
      return {
        pricing_options: [
          {
            plan_id: 1,
            name: 'Basic',
            description: 'One subject per student',
            plan_type: 'basic',
            trial_days: 15,
            monthly_price: 25.00,
            yearly_price: 240.00,
            currency: 'USD',
            features: [
              { name: '1 student profile', description: 'Access for one student' },
              { name: '1 subject access', description: 'Choose one subject' },
              { name: 'Basic progress tracking', description: 'Track learning progress' },
              { name: 'Standard assessments', description: 'Regular assessments' },
              { name: 'Email support', description: 'Customer support via email' }
            ]
          },
          {
            plan_id: 2,
            name: 'Premium',
            description: 'All subjects (Science, Math, English, Humanities) per student',
            plan_type: 'premium',
            trial_days: 15,
            monthly_price: 90.00,
            yearly_price: 864.00,
            currency: 'USD',
            features: [
              { name: 'All subjects access', description: 'Access to all available subjects' },
              { name: 'Advanced progress tracking', description: 'Detailed progress analytics' },
              { name: 'Personalized learning paths', description: 'AI-powered learning paths' },
              { name: 'Priority support', description: '24/7 priority customer support' },
              { name: 'Detailed assessment reports', description: 'Comprehensive assessment analytics' },
              { name: 'Parent coaching sessions', description: 'Regular coaching sessions for parents' }
            ]
          }
        ],
        free_trial_days: 15,
        available_billing_cycles: ['monthly', 'yearly'],
        total_subjects_available: 4
      };
    }

    return pricingData;
  };

  const pricingOptionsData = getPricingOptionsData();

  // Map plan data to the format expected by the UI
  const pricingOptions = {
    basic: {
      name: pricingOptionsData.pricing_options[0].name,
      description: pricingOptionsData.pricing_options[0].description,
      price: billingCycle === 'monthly' ? pricingOptionsData.pricing_options[0].monthly_price : pricingOptionsData.pricing_options[0].yearly_price / 12,
      students: pricingOptionsData.pricing_options[0].plan_type === 'basic' ? 1 : 'Unlimited',
      subjects: pricingOptionsData.pricing_options[0].plan_type === 'basic' ? 1 : 'All',
      features: pricingOptionsData.pricing_options[0].features.map(f => f.name),
      popular: false
    },
    premium: {
      name: pricingOptionsData.pricing_options[1].name,
      description: pricingOptionsData.pricing_options[1].description,
      price: billingCycle === 'monthly' ? pricingOptionsData.pricing_options[1].monthly_price : pricingOptionsData.pricing_options[1].yearly_price / 12,
      students: 'Unlimited',
      subjects: 'All',
      features: pricingOptionsData.pricing_options[1].features.map(f => f.name),
      popular: true
    }
  };

  const handleGetStarted = async (planType: 'basic' | 'premium') => {
    if (!user) {
      navigate('/signup');
      return;
    }

    try {
      // For now, just navigate to billing settings
      // In a full implementation, this would create a subscription
      navigate('/parent-settings?tab=billing');
    } catch (error) {
      console.error('Error starting subscription:', error);
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

        {/* Trial Expired Alert */}
        {trialExpired && (
          <div className="mb-8 bg-red-50 border-2 border-red-200 rounded-xl p-6 text-center">
            <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-red-800 mb-2">Your Free Trial Has Expired</h2>
            <p className="text-red-700">
              To continue accessing Kaihle's learning platform, please choose a subscription plan below.
            </p>
          </div>
        )}

        {/* Trial Banner */}
        {(!user || (billingSummary && billingSummary.total_monthly_cost === 0)) && (
          <div className="mb-12">
            <div className={`border-2 rounded-2xl p-8 text-center ${
              !user ? 'bg-yellow-50 border-yellow-200' :
              billingSummary?.in_free_trial && billingSummary.days_remaining_in_trial > 0 ? 'bg-orange-50 border-orange-200' :
              'bg-red-50 border-red-200'
            }`}>
              <div className="flex items-center justify-center mb-4">
                <span className={`text-white px-3 py-1 rounded-full text-sm font-medium mr-3 ${
                  !user ? 'bg-yellow-600' :
                  billingSummary?.in_free_trial && billingSummary.days_remaining_in_trial > 0 ? 'bg-orange-600' :
                  'bg-red-600'
                }`}>
                  {!user ? '15 DAYS FREE' :
                   billingSummary?.in_free_trial && billingSummary.days_remaining_in_trial > 0 ? `${billingSummary.days_remaining_in_trial} DAYS LEFT` :
                   'TRIAL EXPIRED'}
                </span>
                <h3 className="text-2xl font-bold text-gray-900">
                  {!user ? 'Start with a 15-day free trial' :
                   billingSummary?.in_free_trial && billingSummary.days_remaining_in_trial > 0 ? 'Your trial is expiring soon' :
                   'Your free trial has expired'}
                </h3>
              </div>
              <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
                {!user ? 'Experience the full power of Kaihle with no commitment. Cancel anytime.' :
                 billingSummary?.in_free_trial && billingSummary.days_remaining_in_trial > 0 ? `Your free trial expires in ${billingSummary.days_remaining_in_trial} days. Upgrade now to continue enjoying all features.` :
                 'Please upgrade to a paid plan to continue accessing Kaihle\'s learning platform.'}
              </p>
              <button
                onClick={() => navigate('/plans')}
                className={`text-white px-8 py-4 rounded-xl font-semibold text-lg hover:scale-105 transition-colors ${
                  !user ? 'bg-yellow-600 hover:bg-yellow-700' :
                  billingSummary?.in_free_trial && billingSummary.days_remaining_in_trial > 0 ? 'bg-orange-600 hover:bg-orange-700' :
                  'bg-red-600 hover:bg-red-700'
                }`}
              >
                Upgrade Plan
              </button>
            </div>
          </div>
        )}

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
              Annual Billing (20% off)
            </button>
          </div>
        </div>

        {/* Pricing Plans */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
          {/* Basic Plan */}
          <div className={`bg-white rounded-2xl shadow-lg p-8 flex flex-col ${pricingOptions.basic.popular ? 'ring-2 ring-blue-600' : ''}`}>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">{pricingOptions.basic.name}</h3>
            <p className="text-gray-600 mb-6">{pricingOptions.basic.description}</p>

            <div className="mb-6">
              <span className="text-5xl font-bold text-gray-900">${pricingOptions.basic.price}</span>
              <span className="text-gray-500">/month</span>
              {billingCycle === 'annual' && (
                <p className="text-sm text-gray-500 mt-1">Billed annually at ${pricingOptions.basic.price * 12}/year</p>
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
                handleGetStarted('basic');
              }}
              className={`w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors ${selectedPlan === 'basic' ? 'ring-2 ring-blue-300' : ''}`}
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
                <p className="text-sm text-gray-500 mt-1">Billed annually at ${pricingOptions.premium.price * 12}/year</p>
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
                handleGetStarted('premium');
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
                <h4 className="font-semibold text-gray-900 mb-2">Flexible Pricing Per Student</h4>
                <p className="text-gray-600">Only pay for what you need. Choose from $25 per student for one subject or $80 for all subjects per month, giving you full access to our comprehensive learning platform.</p>
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