import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { PlatformUserTable, PlatformUser } from "./PlatformUserTable";

const student: PlatformUser = {
  id: "u-student",
  school_id: "s1",
  first_name: "Sam",
  last_name: "Student",
  email: "sam@example.com",
  role: "STUDENT",
  is_active: true,
  last_active: null,
  school_name: "Test School",
};

const inactiveTeacher: PlatformUser = {
  ...student,
  id: "u-inactive",
  first_name: "Tia",
  last_name: "Teacher",
  email: "tia@example.com",
  role: "TEACHER",
  is_active: false,
};

const otherAdmin: PlatformUser = {
  ...student,
  id: "u-admin",
  first_name: "Ada",
  last_name: "Admin",
  email: "ada@kaihle.com",
  role: "KAIHLE_ADMIN",
  is_active: true,
};

function renderTable(
  users: PlatformUser[],
  overrides: Partial<React.ComponentProps<typeof PlatformUserTable>> = {},
) {
  const props = {
    users,
    searchQuery: "",
    roleFilter: "ALL" as const,
    onSearchChange: jest.fn(),
    onRoleFilterChange: jest.fn(),
    currentPage: 1,
    totalPages: 1,
    onPageChange: jest.fn(),
    ...overrides,
  };
  render(<PlatformUserTable {...props} />);
  return props;
}

/** The "Log in as" button inside the row belonging to the given user. */
function loginAsButtonFor(email: string): HTMLElement {
  const row = screen.getByText(email).closest("tr") as HTMLElement;
  return within(row).getByRole("button", { name: /log in as/i });
}

describe("PlatformUserTable impersonation action", () => {
  it("calls onImpersonate with the user when Log in as is clicked", () => {
    const onImpersonate = jest.fn();
    renderTable([student], { onImpersonate });

    fireEvent.click(loginAsButtonFor(student.email));

    expect(onImpersonate).toHaveBeenCalledWith(student);
  });

  it("does not trigger the row's edit handler when Log in as is clicked", () => {
    // The row opens the edit drawer; without stopPropagation the drawer would
    // open behind the newly spawned tab.
    const onRowClick = jest.fn();
    const onImpersonate = jest.fn();
    renderTable([student], { onRowClick, onImpersonate });

    fireEvent.click(loginAsButtonFor(student.email));

    expect(onImpersonate).toHaveBeenCalledTimes(1);
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it("disables Log in as for inactive users", () => {
    renderTable([inactiveTeacher], { onImpersonate: jest.fn() });

    expect(loginAsButtonFor(inactiveTeacher.email)).toBeDisabled();
  });

  it("disables Log in as for other Kaihle Admins", () => {
    // Mirrors the backend rule — one platform admin acting as another would be
    // unattributable in the audit trail.
    renderTable([otherAdmin], { onImpersonate: jest.fn() });

    expect(loginAsButtonFor(otherAdmin.email)).toBeDisabled();
  });

  it("disables Log in as for the row currently being minted", () => {
    renderTable([student], {
      onImpersonate: jest.fn(),
      impersonatingUserId: student.id,
    });

    expect(loginAsButtonFor(student.email)).toBeDisabled();
  });

  it("hides Copy link for users who cannot be impersonated", () => {
    renderTable([otherAdmin], {
      onImpersonate: jest.fn(),
      onCopyImpersonateLink: jest.fn(),
    });

    expect(
      screen.queryByRole("button", { name: /copy link/i }),
    ).not.toBeInTheDocument();
  });

  it("renders no impersonation action when no handler is supplied", () => {
    renderTable([student]);

    expect(
      screen.queryByRole("button", { name: /log in as/i }),
    ).not.toBeInTheDocument();
  });
});
