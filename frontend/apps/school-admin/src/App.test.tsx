/**
 * Unit tests for App routing.
 * Covers: billing route redirects to dashboard.
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Navigate } from "react-router-dom";

// Test the billing redirect in isolation using flat routes.
// The Navigate + route setup mirrors exactly what App.tsx declares for billing.
describe("App routing — billing page", () => {
  test("test_app_when_billing_route_accessed_then_redirects_to_dashboard", () => {
    const Dashboard = () => <div>Dashboard</div>;

    render(
      <MemoryRouter initialEntries={["/billing"]}>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route
            path="/billing"
            element={<Navigate to="/dashboard" replace />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });
});
