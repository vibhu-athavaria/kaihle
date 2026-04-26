/**
 * Unit tests for CreateTeacherModal.
 * Covers: rendering, validation, class search / selection, successful submission,
 * error handling, tag removal, and cancel behaviour.
 */
import "@testing-library/jest-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CreateTeacherModal from "../CreateTeacherModal";
import { useCreateUser, useSchoolClasses } from "../../hooks/useSchoolAdmin";
import { toast } from "@kaihle/ui";

jest.mock("../../hooks/useSchoolAdmin");

const mockedUseCreateUser = useCreateUser as jest.MockedFunction<
  typeof useCreateUser
>;
const mockedUseSchoolClasses = useSchoolClasses as jest.MockedFunction<
  typeof useSchoolClasses
>;

function renderModal(open = true) {
  const onOpenChange = jest.fn();
  const utils = render(
    <CreateTeacherModal open={open} onOpenChange={onOpenChange} />,
  );
  return { ...utils, onOpenChange };
}

describe("CreateTeacherModal", () => {
  const classes = [
    {
      id: "c1",
      name: "Grade 10 Math",
      subject_name: "Mathematics",
      grade_level: 10,
      student_count: 24,
    },
    {
      id: "c2",
      name: "Grade 9 Science",
      subject_name: "Science",
      grade_level: 9,
      student_count: 18,
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseSchoolClasses.mockReturnValue({
      data: classes,
    } as ReturnType<typeof useSchoolClasses>);
    mockedUseCreateUser.mockReturnValue({
      mutateAsync: jest.fn().mockResolvedValue({}),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);
  });

  test("test_create_teacher_modal_when_open_then_renders_form_fields", () => {
    renderModal();
    expect(screen.getByPlaceholderText("Rachel")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Morgan")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("r.morgan@school.edu"),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Set a temporary password"),
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search classes…")).toBeInTheDocument();
  });

  test("test_create_teacher_modal_when_closed_then_not_rendered", () => {
    renderModal(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("test_create_teacher_modal_when_empty_submit_then_shows_validation_errors", () => {
    renderModal();
    fireEvent.click(screen.getByRole("button", { name: /create teacher/i }));
    expect(screen.getAllByText("Required").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Valid email required")).toBeInTheDocument();
    expect(screen.getByText("At least 8 characters")).toBeInTheDocument();
  });

  test("test_create_teacher_modal_when_valid_form_then_calls_createUser_and_closes", async () => {
    const mutateAsync = jest.fn().mockResolvedValue({});
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    const { onOpenChange } = renderModal();

    fireEvent.change(screen.getByPlaceholderText("Rachel"), {
      target: { value: "Rachel" },
    });
    fireEvent.change(screen.getByPlaceholderText("Morgan"), {
      target: { value: "Morgan" },
    });
    fireEvent.change(screen.getByPlaceholderText("r.morgan@school.edu"), {
      target: { value: "r.morgan@school.edu" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create teacher/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        first_name: "Rachel",
        last_name: "Morgan",
        email: "r.morgan@school.edu",
        password: "Password123!",
        role: "TEACHER",
        class_ids: undefined,
      });
    });

    expect(toast.success).toHaveBeenCalledWith("Teacher Rachel Morgan created");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test("test_create_teacher_modal_when_class_selected_then_includes_class_ids", async () => {
    const mutateAsync = jest.fn().mockResolvedValue({});
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    renderModal();

    fireEvent.change(screen.getByPlaceholderText("Rachel"), {
      target: { value: "Rachel" },
    });
    fireEvent.change(screen.getByPlaceholderText("Morgan"), {
      target: { value: "Morgan" },
    });
    fireEvent.change(screen.getByPlaceholderText("r.morgan@school.edu"), {
      target: { value: "r.morgan@school.edu" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });

    const checkbox = screen.getByRole("checkbox", {
      name: /grade 10 math/i,
    });
    fireEvent.click(checkbox);

    fireEvent.click(screen.getByRole("button", { name: /create teacher/i }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          role: "TEACHER",
          class_ids: ["c1"],
        }),
      );
    });
  });

  test("test_create_teacher_modal_when_tag_removed_then_class_ids_updated", () => {
    renderModal();

    const checkbox = screen.getByRole("checkbox", {
      name: /grade 10 math/i,
    });
    fireEvent.click(checkbox);

    expect(screen.getAllByText("Grade 10 Math").length).toBe(2);

    const removeBtn = screen.getByRole("button", { name: /×/i });
    fireEvent.click(removeBtn);

    expect(screen.getAllByText("Grade 10 Math").length).toBe(1);
  });

  test("test_create_teacher_modal_when_api_error_then_shows_toast_error", async () => {
    const mutateAsync = jest
      .fn()
      .mockRejectedValue({ response: { data: { detail: "Server error" } } });
    mockedUseCreateUser.mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCreateUser>);

    renderModal();

    fireEvent.change(screen.getByPlaceholderText("Rachel"), {
      target: { value: "Rachel" },
    });
    fireEvent.change(screen.getByPlaceholderText("Morgan"), {
      target: { value: "Morgan" },
    });
    fireEvent.change(screen.getByPlaceholderText("r.morgan@school.edu"), {
      target: { value: "r.morgan@school.edu" },
    });
    fireEvent.change(screen.getByPlaceholderText("Set a temporary password"), {
      target: { value: "Password123!" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create teacher/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Server error");
    });
  });

  test("test_create_teacher_modal_when_cancel_clicked_then_calls_onOpenChange_false", () => {
    const { onOpenChange } = renderModal();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test("test_create_teacher_modal_when_pending_then_submit_disabled", () => {
    mockedUseCreateUser.mockReturnValue({
      mutateAsync: jest.fn(),
      isPending: true,
    } as unknown as ReturnType<typeof useCreateUser>);

    renderModal();
    const submitBtn = screen.getByRole("button", { name: /creating/i });
    expect(submitBtn).toBeDisabled();
  });
});
