/**
 * Unit tests for CreateStudentModal.
 * Covers: rendering, validation, grade selection, password strength,
 * successful submission, error handling, and cancel/reset behaviour.
 */
import "@testing-library/jest-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CreateStudentModal from "../CreateStudentModal";
import { useCreateUser, useGrades } from "../../hooks/useSchoolAdmin";
import { toast } from "@kaihle/ui";

jest.mock("../../hooks/useSchoolAdmin");

const mockedUseCreateUser = useCreateUser as jest.MockedFunction<
  typeof useCreateUser
>;
const mockedUseGrades = useGrades as jest.MockedFunction<typeof useGrades>;

function renderModal(open = true) {
  const onOpenChange = jest.fn();
  const utils = render(
    <CreateStudentModal open={open} onOpenChange={onOpenChange} />,
  );
  return { ...utils, onOpenChange };
}

describe("CreateStudentModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseGrades.mockReturnValue({
      data: [
        { id: "g1", level: 6 },
        { id: "g2", level: 7 },
      ],
    } as ReturnType<typeof useGrades>);
    mockedUseCreateUser.mockReturnValue({
      mutateAsync: jest.fn().mockResolvedValue({}),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);
  });

  test("test_create_student_modal_when_open_then_renders_form_fields", () => {
    renderModal();
    expect(screen.getByPlaceholderText("Aisha")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Al-Rashid")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("aisha@school.edu")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Set a temporary password"),
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText("13")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  test("test_create_student_modal_when_closed_then_not_rendered", () => {
    renderModal(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("test_create_student_modal_when_empty_submit_then_shows_validation_errors", () => {
    renderModal();
    fireEvent.click(screen.getByRole("button", { name: /create student/i }));
    expect(screen.getAllByText("Required").length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getByText("Either email or username is required"),
    ).toBeInTheDocument();
    expect(screen.getByText("At least 8 characters")).toBeInTheDocument();
    expect(screen.getByText("Age between 5 and 25")).toBeInTheDocument();
    expect(screen.getByText("Select a grade")).toBeInTheDocument();
  });

  test("test_create_student_modal_when_short_password_then_shows_password_error", () => {
    renderModal();
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "short" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create student/i }));
    expect(screen.getByText("At least 8 characters")).toBeInTheDocument();
  });

  test("test_create_student_modal_when_password_typed_then_shows_strength_bar", () => {
    renderModal();
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "StrongPass1!" },
    });
    expect(screen.getByText(/strong/i)).toBeInTheDocument();
  });

  test("test_create_student_modal_when_valid_form_then_calls_createUser_and_closes", async () => {
    const mutateAsync = jest.fn().mockResolvedValue({});
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    const { onOpenChange } = renderModal();

    fireEvent.change(screen.getByPlaceholderText("Aisha"), {
      target: { value: "Aisha" },
    });
    fireEvent.change(screen.getByPlaceholderText("Al-Rashid"), {
      target: { value: "Al-Rashid" },
    });
    fireEvent.change(screen.getByPlaceholderText("aisha@school.edu"), {
      target: { value: "aisha@school.edu" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });
    fireEvent.change(screen.getByPlaceholderText("13"), {
      target: { value: "13" },
    });
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "g1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create student/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        first_name: "Aisha",
        last_name: "Al-Rashid",
        email: "aisha@school.edu",
        password: "Password123!",
        role: "STUDENT",
        age: 13,
        grade_id: "g1",
      });
    });

    expect(toast.success).toHaveBeenCalledWith(
      "Student Aisha Al-Rashid created",
    );
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test("test_create_student_modal_when_username_only_then_submits_without_email", async () => {
    const mutateAsync = jest.fn().mockResolvedValue({});
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    const { onOpenChange } = renderModal();

    fireEvent.change(screen.getByPlaceholderText("Aisha"), {
      target: { value: "Aisha" },
    });
    fireEvent.change(screen.getByPlaceholderText("Al-Rashid"), {
      target: { value: "Al-Rashid" },
    });
    fireEvent.change(screen.getByPlaceholderText("aisha.rashid"), {
      target: { value: "aisha.rashid" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });
    fireEvent.change(screen.getByPlaceholderText("13"), {
      target: { value: "13" },
    });
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "g1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create student/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        first_name: "Aisha",
        last_name: "Al-Rashid",
        username: "aisha.rashid",
        password: "Password123!",
        role: "STUDENT",
        age: 13,
        grade_id: "g1",
      });
    });

    expect(toast.success).toHaveBeenCalledWith(
      "Student Aisha Al-Rashid created",
    );
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test("test_create_student_modal_when_api_error_then_shows_toast_error", async () => {
    const mutateAsync = jest
      .fn()
      .mockRejectedValue({ response: { data: { detail: "Email taken" } } });
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    renderModal();

    fireEvent.change(screen.getByPlaceholderText("Aisha"), {
      target: { value: "Aisha" },
    });
    fireEvent.change(screen.getByPlaceholderText("Al-Rashid"), {
      target: { value: "Al-Rashid" },
    });
    fireEvent.change(screen.getByPlaceholderText("aisha@school.edu"), {
      target: { value: "aisha@school.edu" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });
    fireEvent.change(screen.getByPlaceholderText("13"), {
      target: { value: "13" },
    });
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "g1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create student/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Email taken");
    });
  });

  test("test_create_student_modal_when_cancel_clicked_then_calls_onOpenChange_false", () => {
    const { onOpenChange } = renderModal();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test("test_create_student_modal_when_pending_then_submit_disabled", () => {
    mockedUseCreateUser.mockReturnValue({
      mutateAsync: jest.fn(),
      isPending: true,
    } as unknown as ReturnType<typeof useCreateUser>);

    renderModal();
    const submitBtn = screen.getByRole("button", { name: /creating/i });
    expect(submitBtn).toBeDisabled();
  });
});
