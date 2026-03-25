import { render, screen } from "@testing-library/react";
import { Button } from "../components/Button";

describe("Button", () => {
  it("renders with children", () => {
    render(<Button>Click me</Button>);
    expect(
      screen.getByRole("button", { name: /click me/i }),
    ).toBeInTheDocument();
  });

  it("renders primary variant with correct classes", () => {
    render(<Button variant="primary">Primary</Button>);
    const button = screen.getByRole("button");
    expect(button).toHaveClass("bg-brand-primary");
  });

  it("shows loading spinner when loading is true", () => {
    render(<Button loading>Loading</Button>);
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
    expect(button.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("has focus-visible ring classes", () => {
    render(<Button>Focus</Button>);
    const button = screen.getByRole("button");
    expect(button).toHaveClass("focus-visible:ring-brand-primary");
  });

  it("renders secondary variant correctly", () => {
    render(<Button variant="secondary">Secondary</Button>);
    const button = screen.getByRole("button");
    expect(button).toHaveClass("bg-white");
    expect(button).toHaveClass("border-brand-border");
  });

  it("renders danger variant correctly", () => {
    render(<Button variant="danger">Danger</Button>);
    const button = screen.getByRole("button");
    expect(button).toHaveClass("bg-brand-red");
  });

  it("renders different sizes correctly", () => {
    const { rerender } = render(<Button size="sm">Small</Button>);
    expect(screen.getByRole("button")).toHaveClass("px-4");

    rerender(<Button size="lg">Large</Button>);
    expect(screen.getByRole("button")).toHaveClass("px-7");
  });

  it("has min-h-[44px] on md and lg sizes", () => {
    const { rerender } = render(<Button size="md">Medium</Button>);
    expect(screen.getByRole("button")).toHaveClass("min-h-[44px]");

    rerender(<Button size="lg">Large</Button>);
    expect(screen.getByRole("button")).toHaveClass("min-h-[44px]");

    rerender(<Button size="sm">Small</Button>);
    expect(screen.getByRole("button")).not.toHaveClass("min-h-[44px]");
  });
});
