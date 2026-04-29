import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EditUserDrawer } from "./EditUserDrawer";
import { PlatformUser } from "./PlatformUserTable";

const mockUser: PlatformUser = {
  id: "user-1",
  first_name: "Alice",
  last_name: "Smith",
  email: "alice@test.com",
  role: "TEACHER",
  school_id: "school-1",
  school_name: "Test School",
  is_active: true,
  last_active: "2026-04-01T10:00:00Z",
};

const noop = jest.fn().mockResolvedValue(undefined);

function renderDrawer(
  overrides: Partial<Parameters<typeof EditUserDrawer>[0]> = {},
) {
  return render(
    <EditUserDrawer
      user={mockUser}
      isOpen={true}
      onClose={noop}
      onSave={noop}
      onDeactivate={noop}
      {...overrides}
    />,
  );
}

describe("EditUserDrawer", () => {
  beforeEach(() => jest.clearAllMocks());

  test("renders user identity read-only fields", () => {
    renderDrawer();
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("alice@test.com")).toBeInTheDocument();
    expect(screen.getByText("Test School")).toBeInTheDocument();
  });

  test("pre-fills editable fields from user prop", () => {
    renderDrawer();
    expect(screen.getByDisplayValue("Alice")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Smith")).toBeInTheDocument();
  });

  test("calls onSave with updated values on submit", async () => {
    const onSave = jest.fn().mockResolvedValue(undefined);
    renderDrawer({ onSave });

    fireEvent.change(screen.getByLabelText(/first name/i), {
      target: { value: "Alicia" },
    });
    fireEvent.submit(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          userId: "user-1",
          firstName: "Alicia",
          lastName: "Smith",
          role: "TEACHER",
        }),
      );
    });
  });

  test("shows deactivate confirmation on button click", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("button", { name: /deactivate user/i }));
    expect(screen.getByText(/confirm/i)).toBeInTheDocument();
  });

  test("calls onDeactivate after confirmation", async () => {
    const onDeactivate = jest.fn().mockResolvedValue(undefined);
    renderDrawer({ onDeactivate });

    fireEvent.click(screen.getByRole("button", { name: /deactivate user/i }));
    fireEvent.click(screen.getByRole("button", { name: /^deactivate$/i }));

    await waitFor(() => {
      expect(onDeactivate).toHaveBeenCalledWith("user-1", "school-1");
    });
  });

  test("deactivate button is disabled when user is already inactive", () => {
    renderDrawer({ user: { ...mockUser, is_active: false } });
    expect(
      screen.getByRole("button", { name: /user deactivated/i }),
    ).toBeDisabled();
  });

  test("KAIHLE_ADMIN role select is disabled", () => {
    renderDrawer({ user: { ...mockUser, role: "KAIHLE_ADMIN" } });
    expect(screen.getByLabelText(/role/i)).toBeDisabled();
  });

  test("renders empty state when no user provided", () => {
    renderDrawer({ user: null });
    expect(screen.getByText(/no user selected/i)).toBeInTheDocument();
  });

  test("calls onClose when close button clicked", () => {
    const onClose = jest.fn();
    renderDrawer({ onClose });
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
