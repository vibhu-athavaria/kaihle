import { render, screen } from "@testing-library/react";
import { ProgressBar } from "../components/ProgressBar";

describe("ProgressBar", () => {
  it("renders with correct percentage", () => {
    render(<ProgressBar value={73} />);
    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toHaveAttribute("aria-valuenow", "73");
  });

  it("displays label when provided", () => {
    render(<ProgressBar value={50} label="Progress" />);
    expect(screen.getByText("Progress")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("clamps value to 0-100 range", () => {
    render(<ProgressBar value={150} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
  });

  it("handles negative values", () => {
    render(<ProgressBar value={-10} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "0",
    );
  });

  it("renders different sizes", () => {
    const { rerender } = render(<ProgressBar value={50} size="sm" />);
    expect(screen.getByRole("progressbar").parentElement).toHaveClass("h-2");

    rerender(<ProgressBar value={50} size="md" />);
    expect(screen.getByRole("progressbar").parentElement).toHaveClass("h-3");
  });

  it("applies custom color class", () => {
    render(<ProgressBar value={50} colorClass="bg-brand-green" />);
    expect(screen.getByRole("progressbar")).toHaveClass("bg-brand-green");
  });

  it("has smooth transition", () => {
    render(<ProgressBar value={50} />);
    expect(screen.getByRole("progressbar")).toHaveClass("transition-all");
    expect(screen.getByRole("progressbar")).toHaveClass("duration-500");
  });
});
