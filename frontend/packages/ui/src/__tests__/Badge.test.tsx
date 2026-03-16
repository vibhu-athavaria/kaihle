import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "../components/Badge";

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>Status</Badge>);
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders success variant", () => {
    render(<Badge variant="success">Active</Badge>);
    expect(screen.getByText("Active")).toHaveClass("bg-brand-green-light");
    expect(screen.getByText("Active")).toHaveClass("text-brand-green");
  });

  it("renders warning variant", () => {
    render(<Badge variant="warning">Warning</Badge>);
    expect(screen.getByText("Warning")).toHaveClass("bg-brand-amber-light");
  });

  it("renders danger variant", () => {
    render(<Badge variant="danger">Error</Badge>);
    expect(screen.getByText("Error")).toHaveClass("bg-brand-red-light");
  });

  it("renders gold variant", () => {
    render(<Badge variant="gold">Gold</Badge>);
    expect(screen.getByText("Gold")).toHaveClass("bg-brand-gold-light");
  });

  it("shows pulse indicator when pulse is true", () => {
    render(<Badge pulse>Loading</Badge>);
    expect(
      screen.getByText("Loading").querySelector(".animate-pulse"),
    ).toBeInTheDocument();
  });
});
