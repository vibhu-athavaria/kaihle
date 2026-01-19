import { getAuthHeader } from '../lib/authToken';
import { http } from '../lib/http';

// Define the API base URL
const API_BASE_URL = '/api/v1/billing';

export interface PricingOption {
  plan_id: number;
  name: string;
  description: string;
  plan_type: string;
  trial_days: number;
  monthly_price: number;
  yearly_price: number;
  currency: string;
  features: Array<{
    name: string;
    description: string;
  }>;
}

export interface PricingOptionsResponse {
  pricing_options: PricingOption[];
  free_trial_days: number;
  available_billing_cycles: string[];
  total_subjects_available: number;
}

export interface PricingCalculation {
  plan_id: number;
  plan_name: string;
  plan_type: string;
  num_subjects: number;
  billing_cycle: string;
  price: number;
  currency: string;
  base_price: number;
  discount_percentage: number;
  yearly_discount: number;
}

/**
 * Get available pricing options from the backend
 */
export async function getPricingOptions(): Promise<PricingOptionsResponse> {
  try {
    const response = await http.get(`${API_BASE_URL}/pricing/plans`);
    return response.data;
  } catch (error) {
    console.error('Error fetching pricing options:', error);
    // Fallback to hardcoded data if API call fails
    return {
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
}

/**
 * Calculate price for a specific plan and billing cycle
 */
export async function calculatePricing(
  planId: number,
  numSubjects: number = 1,
  billingCycle: string = 'monthly'
): Promise<PricingCalculation> {
  try {
    const response = await http.get(`${API_BASE_URL}/pricing/calculate`, {
      params: {
        plan_id: planId,
        num_subjects: numSubjects,
        billing_cycle: billingCycle
      }
    });
    return response.data;
  } catch (error) {
    console.error('Error calculating pricing:', error);
    throw error;
  }
}

/**
 * Start a free trial for a student
 */
export async function startFreeTrial(studentId: number, subjectId?: number): Promise<any> {
  try {
    const response = await http.post(`${API_BASE_URL}/subscriptions/start-free-trial`, {
      student_id: studentId,
      subject_id: subjectId
    });
    return response.data;
  } catch (error) {
    console.error('Error starting free trial:', error);
    throw error;
  }
}

/**
 * Get subscription plans
 */
export async function getSubscriptionPlans(): Promise<any[]> {
  try {
    const response = await http.get(`${API_BASE_URL}/plans`);
    return response.data;
  } catch (error) {
    console.error('Error fetching subscription plans:', error);
    throw error;
  }
}

/**
 * Create a new subscription
 */
export async function createSubscription(
  studentId: number,
  planId: number,
  billingCycle: string = 'monthly'
): Promise<any> {
  try {
    const response = await http.post(`${API_BASE_URL}/subscriptions`, {
      student_id: studentId,
      plan_id: planId,
      billing_cycle: billingCycle,
      status: 'active'
    });
    return response.data;
  } catch (error) {
    console.error('Error creating subscription:', error);
    throw error;
  }
}