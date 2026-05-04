import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { SlideOverPanel } from "../SlideOverPanel";

describe("SlideOverPanel", () => {
  it("renders title and children when open", () => {
    render(
      <SlideOverPanel open title="Edit class" onClose={jest.fn()}>
        <p>Panel content</p>
      </SlideOverPanel>,
    );
    expect(screen.getByText("Edit class")).toBeInTheDocument();
    expect(screen.getByText("Panel content")).toBeInTheDocument();
  });
  it("does not render when closed", () => {
    render(
      <SlideOverPanel open={false} title="Edit class" onClose={jest.fn()}>
        <p>Panel content</p>
      </SlideOverPanel>,
    );
    expect(screen.queryByText("Edit class")).not.toBeInTheDocument();
  });
  it("calls onClose when close button clicked", () => {
    const onClose = jest.fn();
    render(
      <SlideOverPanel open title="Edit class" onClose={onClose}>
        <p>content</p>
      </SlideOverPanel>,
    );
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
  it("renders footer slot when provided", () => {
    render(
      <SlideOverPanel
        open
        title="Edit class"
        onClose={jest.fn()}
        footer={<button>Save changes</button>}
      >
        <p>content</p>
      </SlideOverPanel>,
    );
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });
});
