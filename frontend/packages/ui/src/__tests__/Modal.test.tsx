import "@testing-library/jest-dom";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "../components/Modal";

function TestModal({ open = true, onOpenChange = jest.fn() }) {
  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Test modal">
      <button>Inside button</button>
    </Modal>
  );
}

describe("Modal", () => {
  it("test_renders_title_when_open", () => {
    render(<TestModal />);
    expect(screen.getByText("Test modal")).toBeInTheDocument();
  });

  it("test_renders_children_when_open", () => {
    render(<TestModal />);
    expect(
      screen.getByRole("button", { name: "Inside button" }),
    ).toBeInTheDocument();
  });

  it("test_not_rendered_when_closed", () => {
    render(<TestModal open={false} />);
    expect(screen.queryByText("Test modal")).not.toBeInTheDocument();
  });

  it("test_close_button_calls_onOpenChange", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();
    render(<TestModal onOpenChange={onOpenChange} />);
    await user.click(screen.getByLabelText("Close"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("test_escape_key_calls_onOpenChange", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();
    render(<TestModal onOpenChange={onOpenChange} />);
    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("test_has_dialog_role", () => {
    render(<TestModal />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("test_title_linked_via_aria_labelledby", () => {
    render(<TestModal />);
    const dialog = screen.getByRole("dialog");
    const titleId = dialog.getAttribute("aria-labelledby");
    expect(titleId).toBeTruthy();
    const title = document.getElementById(titleId!);
    expect(title?.textContent).toBe("Test modal");
  });

  it("test_description_linked_via_aria_describedby_when_provided", () => {
    render(
      <Modal
        open={true}
        onOpenChange={jest.fn()}
        title="Test"
        description="Test desc"
      >
        <div />
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    const descId = dialog.getAttribute("aria-describedby");
    expect(descId).toBeTruthy();
    const desc = document.getElementById(descId!);
    expect(desc?.textContent).toBe("Test desc");
  });

  it("test_hide_close_button_removes_close_button", () => {
    render(<TestModal />);
    expect(screen.getByLabelText("Close")).toBeInTheDocument();

    cleanup();

    render(
      <Modal
        open={true}
        onOpenChange={jest.fn()}
        title="T"
        hideCloseButton={true}
      >
        <div />
      </Modal>,
    );
    expect(screen.queryByLabelText("Close")).not.toBeInTheDocument();
  });

  it("test_custom_title_class_applied", () => {
    render(
      <Modal
        open={true}
        onOpenChange={jest.fn()}
        title="Admin title"
        titleClassName="font-inter text-xl font-bold"
      >
        <div />
      </Modal>,
    );
    const title = screen.getByText("Admin title");
    expect(title).toHaveClass("font-inter");
  });
});
