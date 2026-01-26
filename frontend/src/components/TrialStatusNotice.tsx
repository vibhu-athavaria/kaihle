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
    const fetchSubscriptionSummary = async () => {
      if (!user) {
        setLoading(false);
        return;
      }

      try {
        const response = await http.get('/api/v1/billing/subscriptions');
        setBillingSummary(response.data);

        // Redirect to plans if trial expired and not on billing-related pages
        // const currentPath = window.location.pathname;
        // const isOnBillingPage = currentPath === '/plans' || currentPath === '/parent-settings' || currentPath === '/pricing' || currentPath === '/payment';
        // if (response.data.days_remaining_in_trial <= 0 && !isOnBillingPage) {
        //   navigate('/plans');
        // }
      } catch (error) {
        console.error('Failed to fetch billing summary:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSubscriptionSummary();
  }, [user, navigate]);

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

  // Show banner only for users in active trial (days remaining > 0)
  if (billingSummary.active_subscriptions > 0 || billingSummary.days_remaining_in_trial <= 0) {
    return null;
  }

  return (
    <div className="bg-white text-gray-900 shadow-lg border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between py-3">
          <div className="flex items-center space-x-3">
            <Clock className="w-5 h-5" />
            <div>
               <p className="text-sm font-medium">
                 {billingSummary.days_remaining_in_trial > 0
                   ? `Your trial is expiring in ${billingSummary.days_remaining_in_trial} days. Upgrade to a paid plan to continue learning.`
                   : 'Your trial has expired. Please upgrade the plan to continue.'
                 }
               </p>
             </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={handleUpgrade}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium text-sm hover:bg-blue-700 transition-colors"
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