import { render, screen } from "@testing-library/react";
import { EmptyState } from "../components/EmptyState";

describe("EmptyState", () => {
  it("renders emoji, title, and description", () => {
    render(
      <EmptyState
        emoji="📭"
        title="No items"
        description="You don't have any items yet."
      />,
    );
    expect(screen.getByRole("img", { name: /no items/i })).toHaveTextContent(
      "📭",
    );
    expect(screen.getByText("No items")).toBeInTheDocument();
    expect(screen.getByText(/you don't have any items/i)).toBeInTheDocument();
  });

  it("renders action when provided", () => {
    const action = <button>Add Item</button>;
    render(
      <EmptyState
        emoji="📭"
        title="No items"
        description="You don't have any items yet."
        action={action}
      />,
    );
    expect(
      screen.getByRole("button", { name: /add item/i }),
    ).toBeInTheDocument();
  });

  it("does not render action when not provided", () => {
    render(
      <EmptyState
        emoji="📭"
        title="No items"
        description="You don't have any items yet."
      />,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("has correct typography classes", () => {
    render(
      <EmptyState emoji="📭" title="No items" description="Description text" />,
    );
    expect(screen.getByText("No items")).toHaveClass("font-display");
    expect(screen.getByText("No items")).toHaveClass("font-bold");
    expect(screen.getByText("Description text")).toHaveClass("text-brand-body");
  });
});
