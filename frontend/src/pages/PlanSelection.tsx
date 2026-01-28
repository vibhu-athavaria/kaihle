import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Check, X, ArrowRight, CreditCard, Clock, Users, BookOpen, BarChart2 } from 'lucide-react';
import { getSubscriptionPlans } from '../services/billingService';
import { http } from '../lib/http';

interface BillingSummary {
  active_subscriptions: number;
  trial_subscriptions: number;
  in_free_trial: boolean;
  trial_end_date: string | null;
  trial_start_date: string | null;
  days_remaining_in_trial: number;
  total_monthly_cost: number;
}

interface Student {
  id: number;
  user: {
    full_name: string;
    username: string;
  };
}

export const PlanSelection: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [pricingData, setPricingData] = useState<any>(null);
  const [billingSummary, setBillingSummary] = useState<BillingSummary | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedStudents, setSelectedStudents] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState<'basic' | 'premium'>('basic');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('annual');

  // Fetch subscription plans and billing summary (only for parents)
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch plans first
        const plansResponse = await getSubscriptionPlans();

        // Transform the plans data
        const transformedData = {
          pricing_options: plansResponse.map((plan: any) => ({
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
          free_trial_days: plansResponse[0]?.trial_days || 15,
          available_billing_cycles: ['monthly', 'yearly'],
          total_subjects_available: 4
        };

        setPricingData(transformedData);

        // Try to fetch billing summary and students for parents
        if (user?.role === 'parent') {
          try {
            const [summaryResponse, studentsResponse] = await Promise.all([
              http.get('/api/v1/billing/summary'),
              http.get('/api/v1/users/me/students')
            ]);
            setBillingSummary(summaryResponse.data);
            setStudents(studentsResponse.data);
          } catch (summaryErr) {
            console.error('Failed to fetch billing summary or students:', summaryErr);
            // Don't fail the whole page if summary fails
          }
        }
      } catch (err) {
        console.error('Failed to fetch subscription plans:', err);
        // Set fallback data
        setPricingData({
          pricing_options: [
            {
              plan_id: 1,
              name: 'Basic',
              description: 'Perfect for one student and one subject',
              plan_type: 'basic',
              trial_days: 15,
              monthly_price: 25.00,
              yearly_price: 270.00,
              currency: 'USD',
              features: []
            },
            {
              plan_id: 2,
              name: 'Premium',
              description: 'Best value for families with multiple children',
              plan_type: 'premium',
              trial_days: 15,
              monthly_price: 80.00,
              yearly_price: 864.00,
              currency: 'USD',
              features: []
            }
          ],
          free_trial_days: 15,
          available_billing_cycles: ['monthly', 'yearly'],
          total_subjects_available: 4
        });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [user]);

  // Fallback to hardcoded data if API fails
  const getPricingOptionsData = () => {
    if (loading) {
      return {
        pricing_options: [
          {
            plan_id: 1,
            name: 'Basic',
            description: 'Perfect for one student and one subject',
            plan_type: 'basic',
            trial_days: 15,
            monthly_price: 25.00,
            yearly_price: 240.00,  // 25 * 12 * 0.8 = 240
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
            description: 'Best value for families with multiple children',
            plan_type: 'premium',
            trial_days: 15,
            monthly_price: 90.00,
            yearly_price: 864.00,  // 90 * 12 * 0.8 = 864
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

  // Map plan data to UI format
  const basePriceBasic = billingCycle === 'monthly' ? pricingOptionsData.pricing_options[0].monthly_price : pricingOptionsData.pricing_options[0].yearly_price / 12;
  const basePricePremium = billingCycle === 'monthly' ? pricingOptionsData.pricing_options[1].monthly_price : pricingOptionsData.pricing_options[1].yearly_price / 12;
  const studentCount = selectedStudents.length || 1; // Default to 1 for display

  const pricingOptions = {
    basic: {
      name: pricingOptionsData.pricing_options[0].name,
      description: pricingOptionsData.pricing_options[0].description,
      price: basePriceBasic,
      totalPrice: basePriceBasic * studentCount,
      students: pricingOptionsData.pricing_options[0].plan_type === 'basic' ? 1 : 'Unlimited',
      subjects: pricingOptionsData.pricing_options[0].plan_type === 'basic' ? 1 : 'All',
      features: pricingOptionsData.pricing_options[0].features.map((f: any) => f.name),
      popular: false
    },
    premium: {
      name: pricingOptionsData.pricing_options[1].name,
      description: pricingOptionsData.pricing_options[1].description,
      price: basePricePremium,
      totalPrice: basePricePremium * studentCount,
      students: 'Unlimited',
      subjects: 'All',
      features: pricingOptionsData.pricing_options[1].features.map((f: any) => f.name),
      popular: true
    }
  };

  const handleSelectPlan = async (planType: 'basic' | 'premium') => {
    if (!user) {
      navigate('/signup');
      return;
    }

    if (selectedStudents.length === 0) {
      alert('Please select at least one student for the subscription.');
      return;
    }

    // Navigate to payment page with plan, billing cycle, and selected students
    const studentIds = selectedStudents.join(',');
    navigate(`/payment?plan=${planType}&billing=${billingCycle}&students=${studentIds}`);
  };

  const getCurrentPlanDisplay = () => {
    if (!billingSummary) {
      return {
        name: 'No Active Plan',
        description: 'Choose a plan to get started',
        color: 'gray'
      };
    }

    if (billingSummary.in_free_trial) {
      return {
        name: 'Free Trial',
        description: `${billingSummary.days_remaining_in_trial} days remaining`,
        color: 'orange'
      };
    }

    if (billingSummary.active_subscriptions > 0) {
      return {
        name: 'Premium Plan',
        description: `${billingSummary.active_subscriptions} active subscription(s)`,
        color: 'green'
      };
    }

    return {
      name: 'No Active Plan',
      description: 'Choose a plan to get started',
      color: 'gray'
    };
  };

  const currentPlan = getCurrentPlanDisplay();

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Trial Expired Alert */}
        {user?.role === 'parent' && (!billingSummary || billingSummary.days_remaining_in_trial <= 0) && (
          <div className="mb-8 bg-red-50 border-2 border-red-200 rounded-xl p-6 text-center">
            <h2 className="text-2xl font-bold text-red-800 mb-2">Your Free Trial Has Expired</h2>
            <p className="text-red-700">
              Please upgrade to a plan to continue accessing Kaihle's learning platform.
            </p>
          </div>
        )}

        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">Choose Your Plan</h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Select the perfect plan for your family's learning journey.
          </p>
        </div>

        {/* Current Plan Status */}
        {currentPlan && (
          <div className="mb-12">
            <div className={`bg-${currentPlan.color}-50 border-2 border-${currentPlan.color}-200 rounded-xl p-6 text-center max-w-md mx-auto`}>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Current Plan</h3>
              <p className={`text-2xl font-semibold text-${currentPlan.color}-600 mb-1`}>
                {currentPlan.name}
              </p>
              <p className="text-gray-600">{currentPlan.description}</p>
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

        {/* Student Selection */}
        {user?.role === 'parent' && students.length > 0 && (
          <div className="bg-white rounded-2xl shadow-lg p-8 mb-8 max-w-4xl mx-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">Select Students for Subscription</h2>
            <p className="text-gray-600 mb-6 text-center">Choose which students you want to subscribe. The price will be calculated per student.</p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {students.map((student) => (
                <div
                  key={student.id}
                  className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${
                    selectedStudents.includes(student.id)
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => {
                    setSelectedStudents(prev =>
                      prev.includes(student.id)
                        ? prev.filter(id => id !== student.id)
                        : [...prev, student.id]
                    );
                  }}
                >
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={selectedStudents.includes(student.id)}
                      onChange={() => {}}
                      className="w-5 h-5 text-blue-600 rounded focus:ring-blue-500 mr-3"
                    />
                    <div>
                      <p className="font-medium text-gray-900">{student.user.full_name}</p>
                      <p className="text-sm text-gray-500">@{student.user.username}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {selectedStudents.length > 0 && (
              <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <p className="text-blue-800 font-medium">
                  {selectedStudents.length} student{selectedStudents.length > 1 ? 's' : ''} selected
                </p>
              </div>
            )}
          </div>
        )}

        {/* Pricing Plans */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12 max-w-5xl mx-auto">
          {/* Basic Plan */}
          <div className={`bg-white rounded-2xl shadow-lg p-8 flex flex-col ${pricingOptions.basic.popular ? 'ring-2 ring-blue-600' : ''}`}>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">{pricingOptions.basic.name}</h3>
            <p className="text-gray-600 mb-6">{pricingOptions.basic.description}</p>

            <div className="mb-6">
              <span className="text-5xl font-bold text-gray-900">${pricingOptions.basic.totalPrice}</span>
              <span className="text-gray-500">/month</span>
              <p className="text-sm text-gray-500 mt-1">${pricingOptions.basic.price} per student × {selectedStudents.length || 1} student{selectedStudents.length !== 1 ? 's' : ''}</p>
              {billingCycle === 'annual' && (
                <p className="text-sm text-gray-500">Billed annually at ${pricingOptions.basic.totalPrice * 12}/year</p>
              )}
            </div>

            <div className="mb-8">
              <p className="text-sm text-gray-500 mb-2">Includes:</p>
              <ul className="space-y-3">
                {pricingOptions.basic.features.map((feature: string, index: number) => (
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
                handleSelectPlan('basic');
              }}
              className={`w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors ${selectedPlan === 'basic' ? 'ring-2 ring-blue-300' : ''}`}
            >
              {user ? 'Proceed to Payment' : 'Get Started'}
            </button>
          </div>

          {/* Premium Plan */}
          <div className={`bg-white rounded-2xl shadow-lg p-8 flex flex-col ring-2 ring-blue-600 relative`}>
            <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
              <span className="bg-blue-600 text-white px-4 py-1 rounded-full text-sm font-medium">
                MOST POPULAR
              </span>
            </div>

            <h3 className="text-2xl font-bold text-gray-900 mb-2 mt-4">{pricingOptions.premium.name}</h3>
            <p className="text-gray-600 mb-6">{pricingOptions.premium.description}</p>

            <div className="mb-6">
              <span className="text-5xl font-bold text-gray-900">${pricingOptions.premium.totalPrice}</span>
              <span className="text-gray-500">/month</span>
              <p className="text-sm text-gray-500 mt-1">${pricingOptions.premium.price} per student × {selectedStudents.length || 1} student{selectedStudents.length !== 1 ? 's' : ''}</p>
              {billingCycle === 'annual' && (
                <p className="text-sm text-gray-500">Billed annually at ${pricingOptions.premium.totalPrice * 12}/year</p>
              )}
            </div>

            <div className="mb-8">
              <p className="text-sm text-gray-500 mb-2">Includes:</p>
              <ul className="space-y-3">
                {pricingOptions.premium.features.map((feature: string, index: number) => (
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
                handleSelectPlan('premium');
              }}
              className={`w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors ${selectedPlan === 'premium' ? 'ring-2 ring-blue-300' : ''}`}
            >
              {user ? 'Proceed to Payment' : 'Get Started'}
            </button>
          </div>
        </div>

        {/* Back to Settings */}
        <div className="text-center">
          <button
            onClick={() => navigate('/parent-settings?tab=billing')}
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            ← Back to Billing Settings
          </button>
        </div>
      </div>
    </div>
  );
};