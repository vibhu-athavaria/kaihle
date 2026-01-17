import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { http } from '@/lib/http';
import { useAuth } from '../contexts/AuthContext';
import { Breadcrumb } from '../components/ui/Breadcrumb';
import { Settings, CreditCard, Users } from 'lucide-react';


interface BillingInfo {
  id: number;
  payment_method: string;
  card_last_four: string;
  card_brand: string;
  card_expiry: string;
  is_default: boolean;
}

interface Subscription {
  id: number;
  student_id: number;
  subject_id: number;
  status: string;
  price: number;
  trial_end_date: string;
  end_date: string;
}

interface BillingSummary {
  active_subscriptions: number;
  trial_subscriptions: number;
  past_due_subscriptions: number;
  total_monthly_cost: number;
  next_payment_date: string;
  in_free_trial: boolean;
  trial_end_date: string;
  days_remaining_in_trial: number;
  payment_methods: number;
  has_payment_method: boolean;
}

export const ParentSettings: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'account' | 'billing' | 'notifications'>('account');
  const [billingInfo, setBillingInfo] = useState<BillingInfo[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [billingSummary, setBillingSummary] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddPaymentMethod, setShowAddPaymentMethod] = useState(false);
  const [newPaymentMethod, setNewPaymentMethod] = useState({
    card_number: '',
    card_name: '',
    expiry_date: '',
    cvv: '',
    is_default: true
  });

  useEffect(() => {
    const fetchBillingData = async () => {
      try {
        const token = localStorage.getItem('access_token');
        if (!token) {
          navigate('/parent-login');
          return;
        }

        // Fetch billing information
        const billingResponse = await http.get('/api/v1/billing/billing-info');
        setBillingInfo(billingResponse.data);

        // Fetch subscriptions
        const subscriptionsResponse = await http.get('/api/v1/billing/subscriptions');
        setSubscriptions(subscriptionsResponse.data);

        // Fetch billing summary
        const summaryResponse = await http.get('/api/v1/billing/summary');
        setBillingSummary(summaryResponse.data);

      } catch (err) {
        console.error('Failed to fetch billing data:', err);
        setError('Failed to load billing information');
      } finally {
        setLoading(false);
      }
    };

    fetchBillingData();
  }, [navigate]);

  const handleAddPaymentMethod = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        navigate('/parent-login');
        return;
      }

      // In a real implementation, this would call the payment gateway API
      // For now, we'll simulate adding a payment method
      const newMethod = {
        user_id: user?.id,
        payment_method: 'credit_card',
        card_last_four: newPaymentMethod.card_number.slice(-4),
        card_brand: 'Visa', // This would be detected from the card number
        card_expiry: newPaymentMethod.expiry_date,
        is_default: newPaymentMethod.is_default
      };

      await http.post('/api/v1/billing/billing-info', newMethod);

      // Refresh billing data
      const billingResponse = await http.get('/api/v1/billing/billing-info');
      setBillingInfo(billingResponse.data);

      setShowAddPaymentMethod(false);
      setNewPaymentMethod({
        card_number: '',
        card_name: '',
        expiry_date: '',
        cvv: '',
        is_default: true
      });

    } catch (err) {
      console.error('Failed to add payment method:', err);
      setError('Failed to add payment method');
    }
  };

  const handleCancelSubscription = async (subscriptionId: number) => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        navigate('/parent-login');
        return;
      }

      const confirmCancel = window.confirm('Are you sure you want to cancel this subscription?');
      if (!confirmCancel) return;

      await http.delete(`/api/v1/billing/subscriptions/${subscriptionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Refresh subscriptions
      const subscriptionsResponse = await http.get('/api/v1/billing/subscriptions');
      setSubscriptions(subscriptionsResponse.data);

    } catch (err) {
      console.error('Failed to cancel subscription:', err);
      setError('Failed to cancel subscription');
    }
  };

  const handleStartFreeTrial = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        navigate('/parent-login');
        return;
      }

      // Check if user has any children
      const childrenResponse = await http.get('/api/v1/users/me/students');

      if (childrenResponse.data.length === 0) {
        alert('Please add a child profile first to start a free trial');
        navigate('/add-child');
        return;
      }

      // Start free trial for the first child (in a real app, this would be more sophisticated)
      const studentId = childrenResponse.data[0].id;

      await http.post('/api/v1/billing/subscriptions/start-free-trial', {
        student_id: studentId
      });

      // Refresh data
      const subscriptionsResponse = await http.get('/api/v1/billing/subscriptions');
      setSubscriptions(subscriptionsResponse.data);

      const summaryResponse = await http.get('/api/v1/billing/summary');
      setBillingSummary(summaryResponse.data);

    } catch (err) {
      console.error('Failed to start free trial:', err);
      setError('Failed to start free trial');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading billing information...</p>
        </div>
      </div>
    );
  }

  // Determine breadcrumb items based on active tab
  const getBreadcrumbItems = () => {
    switch (activeTab) {
      case 'account':
        return [{ label: 'Account Information', icon: Settings }];
      case 'billing':
        return [{ label: 'Billing & Subscriptions', icon: CreditCard }];
      case 'notifications':
        return [{ label: 'Notification Preferences', icon: Users }];
      default:
        return [{ label: 'Account Information', icon: Settings }];
    }
  };

  return (
    <div className="min-h-screen bg-blue-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <Breadcrumb role="parent" items={getBreadcrumbItems()} />
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Parent Settings</h1>
          <p className="text-xl text-gray-600">Manage your account, billing, and preferences</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600">
            {error}
          </div>
        )}

        <div className="flex flex-col md:flex-row gap-8">
          {/* Sidebar Navigation */}
          <div className="w-full md:w-64 flex-shrink-0">
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <nav className="flex flex-col">
                <button
                  onClick={() => setActiveTab('account')}
                  className={`px-6 py-4 text-left font-medium ${activeTab === 'account' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
                >
                  Account Information
                </button>
                <button
                  onClick={() => setActiveTab('billing')}
                  className={`px-6 py-4 text-left font-medium ${activeTab === 'billing' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
                >
                  Billing & Subscriptions
                </button>
                <button
                  onClick={() => setActiveTab('notifications')}
                  className={`px-6 py-4 text-left font-medium ${activeTab === 'notifications' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
                >
                  Notifications
                </button>
              </nav>
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1">
            {activeTab === 'account' && (
              <div className="bg-white rounded-xl shadow-sm p-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">Account Information</h2>

                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                    <input
                      type="text"
                      value={user?.full_name || ''}
                      readOnly
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-50 cursor-not-allowed"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    <input
                      type="email"
                      value={user?.email || ''}
                      readOnly
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-50 cursor-not-allowed"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Account Created</label>
                    <input
                      type="text"
                      value={user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'Unknown'}
                      readOnly
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-50 cursor-not-allowed"
                    />
                  </div>

                  <div className="pt-4">
                    <button
                      onClick={() => navigate('/edit-account')}
                      className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
                    >
                      Edit Account Information
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'billing' && (
              <div className="bg-white rounded-xl shadow-sm p-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">Billing & Subscriptions</h2>

                {/* Billing Summary */}
                {billingSummary && (
                  <div className="mb-8">
                    <h3 className="text-xl font-semibold text-gray-900 mb-4">Billing Summary</h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                      <div className="bg-blue-50 rounded-xl p-6">
                        <p className="text-sm text-gray-600 mb-1">Current Status</p>
                        <p className="text-3xl font-bold text-blue-600">
                          {billingSummary.in_free_trial ? 'Free Trial' : 'Active'}
                        </p>
                        {billingSummary.in_free_trial && (
                          <p className="text-sm text-gray-600 mt-2">
                            {billingSummary.days_remaining_in_trial} days remaining
                          </p>
                        )}
                      </div>

                      <div className="bg-green-50 rounded-xl p-6">
                        <p className="text-sm text-gray-600 mb-1">Monthly Cost</p>
                        <p className="text-3xl font-bold text-green-600">
                          ${billingSummary.total_monthly_cost.toFixed(2)}
                        </p>
                        <p className="text-sm text-gray-600 mt-2">
                          {billingSummary.active_subscriptions} active subscription(s)
                        </p>
                      </div>
                    </div>

                    {/* Free Trial CTA */}
                    {!billingSummary.in_free_trial && billingSummary.active_subscriptions === 0 && (
                      <div className="mb-6">
                        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
                          <h4 className="font-semibold text-gray-900 mb-2">Start Your Free Trial</h4>
                          <p className="text-gray-600 mb-4">
                            Get 15 days of full access to Kaihle for free!
                          </p>
                          <button
                            onClick={handleStartFreeTrial}
                            className="bg-yellow-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-yellow-700 transition-colors"
                          >
                            Start Free Trial
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Payment Methods */}
                    <div className="mb-8">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4">
                        <h3 className="text-xl font-semibold text-gray-900">Payment Methods</h3>
                        <button
                          onClick={() => setShowAddPaymentMethod(true)}
                          className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 transition-colors text-sm"
                        >
                          + Add Payment Method
                        </button>
                      </div>

                      {billingInfo.length === 0 ? (
                        <div className="text-center py-8">
                          <p className="text-gray-500 mb-4">No payment methods added</p>
                          <button
                            onClick={() => setShowAddPaymentMethod(true)}
                            className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
                          >
                            Add Payment Method
                          </button>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {billingInfo.map((method) => (
                            <div key={method.id} className="border border-gray-200 rounded-lg p-4 flex items-center justify-between">
                              <div className="flex items-center">
                                <div className="w-12 h-8 bg-blue-600 rounded-md flex items-center justify-center mr-4">
                                  <span className="text-white font-bold text-sm">VISA</span>
                                </div>
                                <div>
                                  <p className="font-medium text-gray-900">
                                    {method.card_brand} ending in {method.card_last_four}
                                  </p>
                                  <p className="text-sm text-gray-500">
                                    Expires {method.card_expiry}
                                  </p>
                                  {method.is_default && (
                                    <span className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full mt-1">
                                      Default
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="flex items-center space-x-2">
                                {!method.is_default && (
                                  <button className="text-blue-600 hover:text-blue-700 text-sm">
                                    Make Default
                                  </button>
                                )}
                                <button className="text-gray-400 hover:text-gray-600">
                                  Edit
                                </button>
                                <button className="text-red-400 hover:text-red-600">
                                  Remove
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Active Subscriptions */}
                    <div className="mb-8">
                      <h3 className="text-xl font-semibold text-gray-900 mb-4">Active Subscriptions</h3>

                      {subscriptions.length === 0 ? (
                        <div className="text-center py-8">
                          <p className="text-gray-500">No active subscriptions</p>
                          {billingSummary?.in_free_trial && (
                            <p className="text-sm text-gray-400 mt-2">
                              You are currently in a free trial period
                            </p>
                          )}
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {subscriptions.map((sub) => (
                            <div key={sub.id} className="border border-gray-200 rounded-lg p-4">
                              <div className="flex flex-col md:flex-row md:items-center md:justify-between">
                                <div className="mb-4 md:mb-0">
                                  <p className="font-medium text-gray-900">
                                    Student ID: {sub.student_id} | Subject ID: {sub.subject_id || 'All'}
                                  </p>
                                  <p className="text-sm text-gray-500 mt-1">
                                    Status: <span className={`font-medium ${sub.status === 'active' ? 'text-green-600' : sub.status === 'trial' ? 'text-blue-600' : 'text-red-600'}`}>
                                      {sub.status}
                                    </span>
                                  </p>
                                  {sub.trial_end_date && (
                                    <p className="text-sm text-gray-500 mt-1">
                                      Trial ends: {new Date(sub.trial_end_date).toLocaleDateString()}
                                    </p>
                                  )}
                                  {sub.end_date && (
                                    <p className="text-sm text-gray-500 mt-1">
                                      Renews on: {new Date(sub.end_date).toLocaleDateString()}
                                    </p>
                                  )}
                                </div>
                                <div className="flex items-center space-x-3">
                                  <span className="text-2xl font-bold text-gray-900">
                                    ${sub.price.toFixed(2)}<span className="text-sm font-normal text-gray-500">/month</span>
                                  </span>
                                  {sub.status !== 'cancelled' && (
                                    <button
                                      onClick={() => handleCancelSubscription(sub.id)}
                                      className="text-red-600 hover:text-red-700 text-sm font-medium"
                                    >
                                      Cancel Subscription
                                    </button>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Billing History */}
                    <div>
                      <h3 className="text-xl font-semibold text-gray-900 mb-4">Billing History</h3>
                      <p className="text-gray-500">No payment history yet</p>
                    </div>
                  </div>
                )}

                {/* Add Payment Method Modal */}
                {showAddPaymentMethod && (
                  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl p-8 max-w-md w-full mx-4">
                      <div className="flex justify-between items-center mb-6">
                        <h3 className="text-xl font-bold text-gray-900">Add Payment Method</h3>
                        <button
                          onClick={() => setShowAddPaymentMethod(false)}
                          className="text-gray-400 hover:text-gray-600"
                        >
                          ×
                        </button>
                      </div>

                      <form onSubmit={handleAddPaymentMethod} className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Card Number
                          </label>
                          <input
                            type="text"
                            value={newPaymentMethod.card_number}
                            onChange={(e) => setNewPaymentMethod({...newPaymentMethod, card_number: e.target.value})}
                            placeholder="1234 1234 1234 1234"
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            required
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Name on Card
                          </label>
                          <input
                            type="text"
                            value={newPaymentMethod.card_name}
                            onChange={(e) => setNewPaymentMethod({...newPaymentMethod, card_name: e.target.value})}
                            placeholder="John Doe"
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            required
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Expiry Date
                            </label>
                            <input
                              type="text"
                              value={newPaymentMethod.expiry_date}
                              onChange={(e) => setNewPaymentMethod({...newPaymentMethod, expiry_date: e.target.value})}
                              placeholder="MM/YY"
                              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                              required
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              CVV
                            </label>
                            <input
                              type="text"
                              value={newPaymentMethod.cvv}
                              onChange={(e) => setNewPaymentMethod({...newPaymentMethod, cvv: e.target.value})}
                              placeholder="123"
                              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                              required
                            />
                          </div>
                        </div>

                        <div className="flex items-center">
                          <input
                            type="checkbox"
                            id="default-payment"
                            checked={newPaymentMethod.is_default}
                            onChange={(e) => setNewPaymentMethod({...newPaymentMethod, is_default: e.target.checked})}
                            className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                          />
                          <label htmlFor="default-payment" className="ml-2 block text-sm text-gray-700">
                            Set as default payment method
                          </label>
                        </div>

                        <div className="pt-4">
                          <button
                            type="submit"
                            className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
                          >
                            Add Payment Method
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'notifications' && (
              <div className="bg-white rounded-xl shadow-sm p-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">Notification Preferences</h2>

                <div className="space-y-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium text-gray-900 mb-1">Email Notifications</h4>
                      <p className="text-sm text-gray-500">Receive updates about your child's progress and billing</p>
                    </div>
                    <input type="checkbox" checked className="h-5 w-5 text-blue-600 border-gray-300 rounded mt-1" />
                  </div>

                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium text-gray-900 mb-1">Push Notifications</h4>
                      <p className="text-sm text-gray-500">Get real-time alerts on your mobile device</p>
                    </div>
                    <input type="checkbox" className="h-5 w-5 text-blue-600 border-gray-300 rounded mt-1" />
                  </div>

                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium text-gray-900 mb-1">Billing Reminders</h4>
                      <p className="text-sm text-gray-500">Receive reminders before payments are due</p>
                    </div>
                    <input type="checkbox" checked className="h-5 w-5 text-blue-600 border-gray-300 rounded mt-1" />
                  </div>

                  <div className="pt-4">
                    <button
                      className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
                    >
                      Save Preferences
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};