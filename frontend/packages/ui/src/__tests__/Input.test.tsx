import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Input } from "../components/Input";

describe("Input", () => {
  it("renders with label", () => {
    render(<Input label="Email" />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it("shows error message when error is provided", () => {
    render(<Input label="Email" error="Invalid email" />);
    expect(screen.getByRole("alert")).toHaveTextContent(/invalid email/i);
  });

  it("sets aria-invalid when error is provided", () => {
    render(<Input label="Email" error="Invalid email" />);
    expect(screen.getByLabelText(/email/i)).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("shows hint when provided without error", () => {
    render(<Input label="Email" hint="We will never share your email" />);
    expect(screen.getByText(/we will never share/i)).toBeInTheDocument();
  });

  it("does not show hint when error is present", () => {
    render(<Input label="Email" error="Invalid" hint="Some hint" />);
    expect(screen.queryByText(/some hint/i)).not.toBeInTheDocument();
  });

  it("applies error border color class", () => {
    render(<Input label="Email" error="Error" />);
    expect(screen.getByLabelText(/email/i)).toHaveClass("border-brand-red");
  });
});
