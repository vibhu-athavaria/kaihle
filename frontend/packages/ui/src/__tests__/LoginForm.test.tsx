import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginForm } from "../LoginForm";

describe("LoginForm", () => {
  const mockOnLogin = jest.fn();
  const mockOnMagicLink = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("renders email and password inputs", () => {
    render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
  });

  test("shows validation error when email is empty on submit", async () => {
    render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

    const submitButton = screen.getByRole("button", { name: /sign in/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/enter a valid email address/i),
      ).toBeInTheDocument();
    });
  });

  test("shows validation error when password is empty on submit", async () => {
    render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

    const emailInput = screen.getByLabelText(/email/i);
    await userEvent.type(emailInput, "test@example.com");

    const submitButton = screen.getByRole("button", { name: /sign in/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });

  test("calls onLogin with email and password on form submit", async () => {
    render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole("button", { name: /sign in/i });

    await userEvent.type(emailInput, "teacher@school.edu");
    await userEvent.type(passwordInput, "password123");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalledWith(
        "teacher@school.edu",
        "password123",
      );
    });
  });

  test("switches to magic link mode when Magic Link tab clicked", async () => {
    render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

    const magicLinkTab = screen.getByRole("button", { name: /magic link/i });
    fireEvent.click(magicLinkTab);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /send login link/i }),
      ).toBeInTheDocument();
    });

    // Password field should not be visible
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  test("calls onMagicLink with email in magic link mode", async () => {
    render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

    // Switch to magic link mode
    const magicLinkTab = screen.getByRole("button", { name: /magic link/i });
    fireEvent.click(magicLinkTab);

    const emailInput = screen.getByLabelText(/email/i);
    const submitButton = screen.getByRole("button", {
      name: /send login link/i,
    });

    await userEvent.type(emailInput, "teacher@school.edu");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnMagicLink).toHaveBeenCalledWith("teacher@school.edu");
    });
  });

  test("shows success message after magic link sent", async () => {
    render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

    // Switch to magic link mode
    const magicLinkTab = screen.getByRole("button", { name: /magic link/i });
    fireEvent.click(magicLinkTab);

    const emailInput = screen.getByLabelText(/email/i);
    const submitButton = screen.getByRole("button", {
      name: /send login link/i,
    });

    await userEvent.type(emailInput, "teacher@school.edu");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/check your inbox/i)).toBeInTheDocument();
      expect(
        screen.getByText(/we sent a login link to your email/i),
      ).toBeInTheDocument();
    });
  });

  test("displays logoLabel in header when provided", () => {
    render(
      <LoginForm
        onLogin={mockOnLogin}
        onMagicLink={mockOnMagicLink}
        logoLabel="Teacher Portal"
      />,
    );

    expect(screen.getByText(/teacher portal/i)).toBeInTheDocument();
  });

  test("shows loading state when isLoading is true", () => {
    render(
      <LoginForm
        onLogin={mockOnLogin}
        onMagicLink={mockOnMagicLink}
        isLoading={true}
      />,
    );

    const submitButton = screen.getByRole("button", { name: /sign in/i });
    expect(submitButton).toBeDisabled();
  });

  test("displays error message when login fails", async () => {
    mockOnLogin.mockRejectedValue(new Error("Invalid credentials"));

    render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole("button", { name: /sign in/i });

    await userEvent.type(emailInput, "wrong@example.com");
    await userEvent.type(passwordInput, "wrongpassword");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/invalid email or password/i),
      ).toBeInTheDocument();
    });
  });

  describe("Accessibility", () => {
    test("all inputs have visible labels", () => {
      render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);

      expect(emailInput).toHaveAttribute("id", "email");
      expect(passwordInput).toHaveAttribute("id", "password");
    });

    test("email input has correct autocomplete attribute", () => {
      render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toHaveAttribute("autocomplete", "email");
    });

    test("password input has correct autocomplete attribute", () => {
      render(<LoginForm onLogin={mockOnLogin} onMagicLink={mockOnMagicLink} />);

      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toHaveAttribute("autocomplete", "current-password");
    });
  });
});
