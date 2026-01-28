import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { loadStripe } from '@stripe/stripe-js';
import {
  Elements,
  CardElement,
  useStripe,
  useElements
} from '@stripe/react-stripe-js';
import { http } from '../lib/http';
import { Check, CreditCard, Lock, ArrowLeft } from 'lucide-react';

// Initialize Stripe (replace with your publishable key)
const stripePromise = loadStripe('pk_test_your_stripe_publishable_key');

interface Student {
  id: number;
  user: {
    full_name: string;
    username: string;
  };
}

interface PaymentFormProps {
  planId: string;
  billingCycle: string;
  planName: string;
  price: number;
  selectedStudents: Student[];
}

const PaymentForm: React.FC<PaymentFormProps> = ({
  planId,
  billingCycle,
  planName,
  price,
  selectedStudents
}) => {
  const stripe = useStripe();
  const elements = useElements();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [billingDetails, setBillingDetails] = useState({
    name: '',
    email: user?.email || '',
    address: {
      line1: '',
      city: '',
      state: '',
      postal_code: '',
      country: 'US'
    }
  });

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!stripe || !elements) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Create payment intent on backend
      const response = await http.post('/api/v1/billing/create-payment-intent', {
        plan_id: planId,
        billing_cycle: billingCycle,
        student_ids: selectedStudents.map(s => s.id),
        billing_details: billingDetails
      });

      const { client_secret } = response.data;

      // Confirm payment with Stripe
      const { error: stripeError } = await stripe.confirmCardPayment(client_secret, {
        payment_method: {
          card: elements.getElement(CardElement)!,
          billing_details: {
            name: billingDetails.name,
            email: billingDetails.email,
            address: billingDetails.address
          }
        }
      });

      if (stripeError) {
        setError(stripeError.message || 'Payment failed');
      } else {
        // Payment succeeded
        navigate('/payment-success');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Payment failed');
    } finally {
      setLoading(false);
    }
  };

  const cardStyle = {
    style: {
      base: {
        fontSize: '16px',
        color: '#424770',
        '::placeholder': {
          color: '#aab7c4',
        },
      },
      invalid: {
        color: '#9e2146',
      },
    },
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-xl shadow-lg p-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Complete Your Payment</h2>
          <p className="text-gray-600">Secure payment powered by Stripe</p>
        </div>

        {/* Order Summary */}
        <div className="bg-gray-50 rounded-lg p-6 mb-8">
          <h3 className="font-semibold text-gray-900 mb-4">Order Summary</h3>
          <div className="flex justify-between items-center mb-4">
            <div>
              <p className="font-medium">{planName}</p>
              <p className="text-sm text-gray-600 capitalize">{billingCycle} billing</p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold">${price}</p>
              <p className="text-sm text-gray-600">per {billingCycle === 'monthly' ? 'month' : 'year'}</p>
            </div>
          </div>

          <div className="border-t pt-4">
            <h4 className="font-medium text-gray-900 mb-2">Students Included:</h4>
            <ul className="space-y-1">
              {selectedStudents.map((student) => (
                <li key={student.id} className="text-sm text-gray-600">
                  • {student.user.full_name} (@{student.user.username})
                </li>
              ))}
            </ul>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Billing Details */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Billing Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  value={billingDetails.name}
                  onChange={(e) => setBillingDetails({...billingDetails, name: e.target.value})}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={billingDetails.email}
                  onChange={(e) => setBillingDetails({...billingDetails, email: e.target.value})}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Billing Address
              </label>
              <input
                type="text"
                placeholder="Street address"
                value={billingDetails.address.line1}
                onChange={(e) => setBillingDetails({
                  ...billingDetails,
                  address: {...billingDetails.address, line1: e.target.value}
                })}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-3"
                required
              />
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <input
                  type="text"
                  placeholder="City"
                  value={billingDetails.address.city}
                  onChange={(e) => setBillingDetails({
                    ...billingDetails,
                    address: {...billingDetails.address, city: e.target.value}
                  })}
                  className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
                <input
                  type="text"
                  placeholder="State"
                  value={billingDetails.address.state}
                  onChange={(e) => setBillingDetails({
                    ...billingDetails,
                    address: {...billingDetails.address, state: e.target.value}
                  })}
                  className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
                <input
                  type="text"
                  placeholder="ZIP"
                  value={billingDetails.address.postal_code}
                  onChange={(e) => setBillingDetails({
                    ...billingDetails,
                    address: {...billingDetails.address, postal_code: e.target.value}
                  })}
                  className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>
            </div>
          </div>

          {/* Payment Method */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Payment Method</h3>
            <div className="border border-gray-300 rounded-lg p-4">
              <div className="flex items-center mb-4">
                <CreditCard className="w-5 h-5 text-gray-600 mr-2" />
                <span className="font-medium text-gray-900">Credit or Debit Card</span>
              </div>
              <CardElement options={cardStyle} className="p-3 border border-gray-300 rounded-lg" />
            </div>
            <div className="flex items-center mt-2 text-sm text-gray-600">
              <Lock className="w-4 h-4 mr-1" />
              <span>Your payment information is secure and encrypted</span>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-600">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!stripe || loading}
            className="w-full bg-blue-600 text-white py-4 px-6 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                Processing Payment...
              </>
            ) : (
              <>
                <Lock className="w-5 h-5 mr-2" />
                Pay ${price}
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

export const PaymentPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [selectedStudents, setSelectedStudents] = useState<Student[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(true);

  const planId = searchParams.get('plan') || 'basic';
  const billingCycle = searchParams.get('billing') || 'monthly';
  const studentIdsParam = searchParams.get('students') || '';

  // Mock plan data - in real app, fetch from API
  const planData = {
    basic: {
      name: 'Basic Plan',
      monthly_price: 25,
      yearly_price: 270
    },
    premium: {
      name: 'Premium Plan',
      monthly_price: 80,
      yearly_price: 864
    }
  };

  const selectedPlan = planData[planId as keyof typeof planData];
  const basePrice = billingCycle === 'monthly' ? selectedPlan.monthly_price : Math.round(selectedPlan.yearly_price / 12);
  const price = basePrice * selectedStudents.length;

  // Fetch selected students
  useEffect(() => {
    const fetchSelectedStudents = async () => {
      if (!studentIdsParam || !user?.role === 'parent') {
        setLoadingStudents(false);
        return;
      }

      try {
        const studentIds = studentIdsParam.split(',').map(id => parseInt(id));
        const allStudents = await http.get('/api/v1/users/me/students');
        const selected = allStudents.data.filter((student: Student) =>
          studentIds.includes(student.id)
        );
        setSelectedStudents(selected);
      } catch (error) {
        console.error('Failed to fetch selected students:', error);
      } finally {
        setLoadingStudents(false);
      }
    };

    fetchSelectedStudents();
  }, [studentIdsParam, user]);

  if (!user) {
    navigate('/parent-login');
    return null;
  }

  if (loadingStudents) {
    return (
      <div className="min-h-screen bg-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading payment details...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <button
          onClick={() => navigate('/plans')}
          className="flex items-center text-blue-600 hover:text-blue-700 mb-8"
        >
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back to Plans
        </button>

        <Elements stripe={stripePromise}>
          <PaymentForm
            planId={planId}
            billingCycle={billingCycle}
            planName={selectedPlan.name}
            price={price}
            selectedStudents={selectedStudents}
          />
        </Elements>
      </div>
    </div>
  );
};