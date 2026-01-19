#!/usr/bin/env python3
"""
Test script for the new billing API endpoints
"""

import requests
import json

def test_api_endpoints():
    base_url = 'http://localhost:8000/api/v1/billing'

    print("Testing Kaihle Billing API Endpoints")
    print("=" * 50)

    # Test 1: Get pricing options
    print("\n1. Testing GET /pricing/plans")
    try:
        response = requests.get(f'{base_url}/pricing/plans')
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: Found {len(data['pricing_options'])} pricing options")

            for plan in data['pricing_options']:
                print(f"\n   Plan: {plan['name']}")
                print(f"   - Type: {plan['plan_type']}")
                print(f"   - Monthly: ${plan['monthly_price']}")
                print(f"   - Yearly: ${plan['yearly_price']}")
                print(f"   - Trial: {plan['trial_days']} days")
                print(f"   - Features: {len(plan['features'])}")
                for feature in plan['features']:
                    print(f"     • {feature['name']}")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")

    # Test 2: Calculate pricing for Basic plan
    print("\n2. Testing GET /pricing/calculate (Basic Plan)")
    try:
        params = {
            'plan_id': 1,
            'num_subjects': 1,
            'billing_cycle': 'monthly'
        }
        response = requests.get(f'{base_url}/pricing/calculate', params=params)
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: Price calculation for Basic Plan")
            print(f"   - Plan: {data['plan_name']}")
            print(f"   - Price: ${data['price']} {data['billing_cycle']}")
            print(f"   - Base Price: ${data['base_price']}")
            print(f"   - Discount: {data['discount_percentage']}%")
            print(f"   - Yearly Discount: {data['yearly_discount']}%")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")

    # Test 3: Calculate pricing for Premium plan
    print("\n3. Testing GET /pricing/calculate (Premium Plan)")
    try:
        params = {
            'plan_id': 2,
            'billing_cycle': 'monthly'
        }
        response = requests.get(f'{base_url}/pricing/calculate', params=params)
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: Price calculation for Premium Plan")
            print(f"   - Plan: {data['plan_name']}")
            print(f"   - Price: ${data['price']} {data['billing_cycle']}")
            print(f"   - Base Price: ${data['base_price']}")
            print(f"   - Discount: {data['discount_percentage']}%")
            print(f"   - Yearly Discount: {data['yearly_discount']}%")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")

    # Test 4: Get all subscription plans
    print("\n4. Testing GET /plans")
    try:
        response = requests.get(f'{base_url}/plans')
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: Found {len(data)} subscription plans")
            for plan in data:
                print(f"   - {plan['name']} (ID: {plan['id']}, Type: {plan['plan_type']})")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")

    print("\n" + "=" * 50)
    print("API Testing Complete!")

if __name__ == "__main__":
    test_api_endpoints()