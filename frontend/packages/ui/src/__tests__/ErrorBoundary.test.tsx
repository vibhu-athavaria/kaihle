import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "../components/ErrorBoundary";
import userEvent from "@testing-library/user-event";
import React from "react";

/** Component that throws an error for testing the ErrorBoundary */
function ThrowError({ message }: { message?: string }) {
  throw new Error(message ?? "Test error");
}

describe("ErrorBoundary", () => {
  it("renders_children_when_no_error_is_thrown", () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">正常的孩子</div>
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("shows_fallback_when_child_throws_an_error", () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("displays_error_message_in_fallback", () => {
    const errorMessage = "Database connection failed";
    render(
      <ErrorBoundary>
        <ThrowError message={errorMessage} />
      </ErrorBoundary>,
    );
    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it("renders_custom_fallback_when_provided", () => {
    const customFallback = (
      <div data-testid="custom-fallback">Custom error</div>
    );
    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
  });

  it("calls_onError_callback_when_error_is_caught", () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <ThrowError />
      </ErrorBoundary>,
    );
    expect(onError).toHaveBeenCalledTimes(1);
    const [error, errorInfo] = onError.mock.calls[0];
    expect(error).toBeInstanceOf(Error);
    expect(errorInfo).toHaveProperty("componentStack");
  });

  it("has_role_alert_attribute_for_accessibility", () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
    );
    const fallback = screen.getByRole("alert");
    expect(fallback).toBeInTheDocument();
  });

  it("has_aria_live_assertive_for_screen_reader_announcement", () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
    );
    const fallback = screen.getByRole("alert");
    expect(fallback).toHaveAttribute("aria-live", "assertive");
  });

  it("uses_font_inter_for_kaihle_admin_role", () => {
    render(
      <ErrorBoundary role="kaihle-admin">
        <ThrowError />
      </ErrorBoundary>,
    );
    const fallback = screen.getByRole("alert");
    expect(fallback).toHaveClass("font-['Inter']");
  });

  it("uses_font_display_for_teacher_role", () => {
    render(
      <ErrorBoundary role="teacher">
        <ThrowError />
      </ErrorBoundary>,
    );
    const fallback = screen.getByRole("alert");
    expect(fallback).toHaveClass("font-sans");
  });

  it("has_reload_page_button", () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
    );
    expect(
      screen.getByRole("button", { name: /reload page/i }),
    ).toBeInTheDocument();
  });

  it("reload_button_triggers_page_reload", async () => {
    const user = userEvent.setup();
    const reloadMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { reload: reloadMock },
      writable: true,
    });

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>,
    );

    await user.click(screen.getByRole("button", { name: /reload page/i }));
    expect(reloadMock).toHaveBeenCalledTimes(1);
  });

  it("renders_with_role_student", () => {
    render(
      <ErrorBoundary role="student">
        <ThrowError />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders_with_role_parent", () => {
    render(
      <ErrorBoundary role="parent">
        <ThrowError />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders_with_role_school_admin", () => {
    render(
      <ErrorBoundary role="school-admin">
        <ThrowError />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders_with_role_onboarding", () => {
    render(
      <ErrorBoundary role="onboarding">
        <ThrowError />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
