import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { X, Clock, CreditCard } from 'lucide-react';
import { http } from '../lib/http';

interface BillingSummary {
  active_subscriptions: number;
  trial_subscriptions: number;
  in_free_trial: boolean;
  trial_end_date: string | null;
  trial_start_date: string | null;
  days_remaining_in_trial: number;
}

export const TrialStatusNotice: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [billingSummary, setBillingSummary] = useState<BillingSummary | null>(null);
  const [isDismissed, setIsDismissed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBillingSummary = async () => {
      if (!user) {
        setLoading(false);
        return;
      }

      try {
        const response = await http.get('/api/v1/billing/summary');
        setBillingSummary(response.data);
      } catch (error) {
        console.error('Failed to fetch billing summary:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchBillingSummary();
  }, [user]);

  useEffect(() => {
    // Check if notice was dismissed recently (within 24 hours)
    const dismissedAt = localStorage.getItem('trial_notice_dismissed_at');
    if (dismissedAt) {
      const dismissedTime = new Date(dismissedAt).getTime();
      const now = new Date().getTime();
      const hoursDiff = (now - dismissedTime) / (1000 * 60 * 60);

      if (hoursDiff < 24) {
        setIsDismissed(true);
      } else {
        // Clear expired dismissal
        localStorage.removeItem('trial_notice_dismissed_at');
      }
    }
  }, []);

  const handleDismiss = () => {
    setIsDismissed(true);
    localStorage.setItem('trial_notice_dismissed_at', new Date().toISOString());
  };

  const handleUpgrade = () => {
    navigate('/plans'); // Navigate to plan selection page
  };

  // Don't show if not logged in, loading, dismissed, or user has active paid subscription
  if (!user || loading || isDismissed || !billingSummary) {
    return null;
  }

  // Don't show if user has active paid subscriptions
  if (billingSummary.active_subscriptions > 0 && !billingSummary.in_free_trial) {
    return null;
  }

  const isTrialExpired = billingSummary.days_remaining_in_trial <= 0;
  const showNotice = billingSummary.in_free_trial || isTrialExpired;

  if (!showNotice) {
    return null;
  }

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between py-3">
          <div className="flex items-center space-x-3">
            {isTrialExpired ? (
              <CreditCard className="w-5 h-5" />
            ) : (
              <Clock className="w-5 h-5" />
            )}
            <div>
              {isTrialExpired ? (
                <p className="text-sm font-medium">
                  Your free trial has expired. Upgrade to a paid plan to continue learning.
                </p>
              ) : (
                <p className="text-sm font-medium">
                  {billingSummary.days_remaining_in_trial} days remaining in your free trial
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={handleUpgrade}
              className="bg-white text-blue-600 px-4 py-2 rounded-lg font-medium text-sm hover:bg-gray-50 transition-colors"
            >
              Upgrade Plan
            </button>
            <button
              onClick={handleDismiss}
              className="text-white hover:text-gray-200 transition-colors"
              aria-label="Dismiss notice"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};