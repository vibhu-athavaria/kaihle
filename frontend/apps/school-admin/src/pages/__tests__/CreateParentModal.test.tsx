/**
 * Unit tests for CreateParentModal.
 * Covers: rendering, validation, student search / selection, successful submission,
 * error handling, tag removal, and cancel behaviour.
 */
import "@testing-library/jest-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CreateParentModal from "../CreateParentModal";
import { useCreateUser, useSchoolStudents } from "../../hooks/useSchoolAdmin";
import { toast } from "@kaihle/ui";

jest.mock("../../hooks/useSchoolAdmin");

const mockedUseCreateUser = useCreateUser as jest.MockedFunction<
  typeof useCreateUser
>;
const mockedUseSchoolStudents = useSchoolStudents as jest.MockedFunction<
  typeof useSchoolStudents
>;

function renderModal(open = true) {
  const onOpenChange = jest.fn();
  const utils = render(
    <CreateParentModal open={open} onOpenChange={onOpenChange} />,
  );
  return { ...utils, onOpenChange };
}

describe("CreateParentModal", () => {
  const students = [
    {
      id: "s1",
      first_name: "Aisha",
      last_name: "Al-Rashid",
      class_count: 3,
    },
    {
      id: "s2",
      first_name: "Omar",
      last_name: "Hassan",
      class_count: 2,
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseSchoolStudents.mockReturnValue({
      data: students,
    } as ReturnType<typeof useSchoolStudents>);
    mockedUseCreateUser.mockReturnValue({
      mutateAsync: jest.fn().mockResolvedValue({}),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);
  });

  test("test_create_parent_modal_when_open_then_renders_form_fields", () => {
    renderModal();
    expect(screen.getByPlaceholderText("James")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Al-Rashid")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("james@gmail.com")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Set a temporary password"),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Search by student name…"),
    ).toBeInTheDocument();
  });

  test("test_create_parent_modal_when_closed_then_not_rendered", () => {
    renderModal(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("test_create_parent_modal_when_empty_submit_then_shows_validation_errors", () => {
    renderModal();
    fireEvent.click(screen.getByRole("button", { name: /create parent/i }));
    expect(screen.getAllByText("Required").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Valid email required")).toBeInTheDocument();
    expect(screen.getByText("At least 8 characters")).toBeInTheDocument();
  });

  test("test_create_parent_modal_when_valid_form_then_calls_createUser_and_closes", async () => {
    const mutateAsync = jest.fn().mockResolvedValue({});
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    const { onOpenChange } = renderModal();

    fireEvent.change(screen.getByPlaceholderText("James"), {
      target: { value: "James" },
    });
    fireEvent.change(screen.getByPlaceholderText("Al-Rashid"), {
      target: { value: "Al-Rashid" },
    });
    fireEvent.change(screen.getByPlaceholderText("james@gmail.com"), {
      target: { value: "james@gmail.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create parent/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        first_name: "James",
        last_name: "Al-Rashid",
        email: "james@gmail.com",
        password: "Password123!",
        role: "PARENT",
        student_ids: undefined,
      });
    });

    expect(toast.success).toHaveBeenCalledWith(
      "Parent James Al-Rashid created",
    );
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test("test_create_parent_modal_when_student_selected_then_includes_student_ids", async () => {
    const mutateAsync = jest.fn().mockResolvedValue({});
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    renderModal();

    fireEvent.change(screen.getByPlaceholderText("James"), {
      target: { value: "James" },
    });
    fireEvent.change(screen.getByPlaceholderText("Al-Rashid"), {
      target: { value: "Al-Rashid" },
    });
    fireEvent.change(screen.getByPlaceholderText("james@gmail.com"), {
      target: { value: "james@gmail.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });

    const checkbox = screen.getByRole("checkbox", {
      name: /aisha al-rashid/i,
    });
    fireEvent.click(checkbox);

    fireEvent.click(screen.getByRole("button", { name: /create parent/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          role: "PARENT",
          student_ids: ["s1"],
        }),
      );
    });
  });

  test("test_create_parent_modal_when_tag_removed_then_student_ids_updated", () => {
    renderModal();

    const checkbox = screen.getByRole("checkbox", {
      name: /aisha al-rashid/i,
    });
    fireEvent.click(checkbox);

    expect(screen.getAllByText("Aisha Al-Rashid").length).toBe(2);

    const removeBtn = screen.getByRole("button", { name: /×/i });
    fireEvent.click(removeBtn);

    expect(screen.getAllByText("Aisha Al-Rashid").length).toBe(1);
  });

  test("test_create_parent_modal_when_api_error_then_shows_toast_error", async () => {
    const mutateAsync = jest
      .fn()
      .mockRejectedValue({ response: { data: { detail: "Server error" } } });
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    renderModal();

    fireEvent.change(screen.getByPlaceholderText("James"), {
      target: { value: "James" },
    });
    fireEvent.change(screen.getByPlaceholderText("Al-Rashid"), {
      target: { value: "Al-Rashid" },
    });
    fireEvent.change(screen.getByPlaceholderText("james@gmail.com"), {
      target: { value: "james@gmail.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create parent/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Server error");
    });
  });

  test("test_create_parent_modal_when_cancel_clicked_then_calls_onOpenChange_false", () => {
    const { onOpenChange } = renderModal();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test("test_create_parent_modal_when_pending_then_submit_disabled", () => {
    mockedUseCreateUser.mockReturnValue({
      mutateAsync: jest.fn(),
      isPending: true,
    } as unknown as ReturnType<typeof useCreateUser>);

    renderModal();
    const submitBtn = screen.getByRole("button", { name: /creating/i });
    expect(submitBtn).toBeDisabled();
  });
});
