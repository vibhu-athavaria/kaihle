import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { InlineEditName } from "../components/settings/InlineEditName";
import { ChildrenSection } from "../components/settings/ChildrenSection";

describe("InlineEditName (parent variant)", () => {
  it("test_save_disabled_when_first_name_empty", () => {
    render(
      <InlineEditName
        currentFirstName="Emma"
        currentLastName="Chen"
        onSave={jest.fn()}
        onCancel={jest.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/first name/i), {
      target: { value: "" },
    });
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  it("test_cancel_does_not_call_onSave", () => {
    const onSave = jest.fn();
    render(
      <InlineEditName
        currentFirstName="Emma"
        currentLastName="Chen"
        onSave={onSave}
        onCancel={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onSave).not.toHaveBeenCalled();
  });

  it("test_save_callss_onSave_with_trimmed_values", async () => {
    const onSave = jest.fn().mockResolvedValue(undefined);
    render(
      <InlineEditName
        currentFirstName="Emma"
        currentLastName="Chen"
        onSave={onSave}
        onCancel={jest.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/first name/i), {
      target: { value: "  Sarah  " },
    });
    fireEvent.change(screen.getByLabelText(/last name/i), {
      target: { value: "  Jones  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("Sarah", "Jones");
    });
  });

  it("test_renders_with_current_values", () => {
    render(
      <InlineEditName
        currentFirstName="Emma"
        currentLastName="Chen"
        onSave={jest.fn()}
        onCancel={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/first name/i)).toHaveValue("Emma");
    expect(screen.getByLabelText(/last name/i)).toHaveValue("Chen");
  });
});

describe("ChildrenSection", () => {
  it("test_renders_child_name_and_grade", () => {
    const children = [
      {
        id: "1",
        first_name: "Emma",
        last_name: "Chen",
        grade: "Grade 8",
        school_name: "Bali IS",
      },
    ];
    render(<ChildrenSection items={children} />);
    expect(screen.getByText("Emma Chen")).toBeInTheDocument();
    expect(screen.getByText(/Grade 8/)).toBeInTheDocument();
  });

  it("test_empty_state_when_no_children", () => {
    render(<ChildrenSection items={[]} />);
    expect(screen.getByText(/no children linked/i)).toBeInTheDocument();
  });

  it("test_avatar_initials_are_correct", () => {
    const children = [
      {
        id: "1",
        first_name: "Emma",
        last_name: "Chen",
        grade: "Grade 8",
        school_name: "Bali IS",
      },
    ];
    const { container } = render(<ChildrenSection items={children} />);
    // Avatar shows "EC" for Emma Chen
    expect(container.querySelector('[aria-hidden="true"]')?.textContent).toBe(
      "EC",
    );
  });

  it("test_renders_school_name", () => {
    const children = [
      {
        id: "1",
        first_name: "Emma",
        last_name: "Chen",
        grade: "Grade 8",
        school_name: "Bali International School",
      },
    ];
    render(<ChildrenSection items={children} />);
    expect(screen.getByText(/Bali International School/)).toBeInTheDocument();
  });

  it("test_renders_section_heading", () => {
    render(<ChildrenSection items={[]} />);
    expect(
      screen.getByRole("heading", { name: /my children/i }),
    ).toBeInTheDocument();
  });

  it("test_renders_contact_school_admin_note", () => {
    render(<ChildrenSection items={[]} />);
    expect(screen.getByText(/contact your school admin/i)).toBeInTheDocument();
  });

  it("test_renders_multiple_children", () => {
    const children = [
      {
        id: "1",
        first_name: "Emma",
        last_name: "Chen",
        grade: "Grade 8",
        school_name: "Bali IS",
      },
      {
        id: "2",
        first_name: "Lucas",
        last_name: "Chen",
        grade: "Grade 6",
        school_name: "Bali IS",
      },
    ];
    render(<ChildrenSection items={children} />);
    expect(screen.getByText("Emma Chen")).toBeInTheDocument();
    expect(screen.getByText("Lucas Chen")).toBeInTheDocument();
  });
});
