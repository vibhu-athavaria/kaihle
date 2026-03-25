import { render, screen } from "@testing-library/react";
import { Skeleton, SkeletonCard } from "../components/Skeleton";

describe("Skeleton", () => {
  it("renders basic skeleton", () => {
    render(<Skeleton className="w-10" />);
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toHaveClass("animate-pulse");
    expect(skeleton).toHaveClass("bg-brand-border");
  });

  it("renders skeleton with lines", () => {
    render(<Skeleton lines={3} />);
    const container = document.querySelector(".animate-pulse");
    expect(container).toBeInTheDocument();
  });
});

describe("SkeletonCard", () => {
  it("renders skeleton card", () => {
    render(<SkeletonCard />);
    const card = document.querySelector(".animate-pulse");
    expect(card).toHaveClass("bg-white");
    expect(card).toHaveClass("rounded-2xl");
  });
});
