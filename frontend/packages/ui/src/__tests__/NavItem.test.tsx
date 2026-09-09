import { render, screen } from "@testing-library/react";
import { NavItem } from "../components/nav/NavItem";
import { Home } from "lucide-react";

describe("NavItem", () => {
  it("applies gold tint class when active for teacher variant", () => {
    render(
      <NavItem
        label="Dashboard"
        href="/teacher/dashboard"
        icon={Home}
        isActive={true}
        variant="teacher"
      />,
    );

    const link = screen.getByRole("link", { name: /dashboard/i });
    // Token, not raw hex. The component was correctly refactored to
    // bg-role-teacher-nav-active (= #fffbeb) per DESIGN_SYSTEM §1: "All hex values live
    // only in tailwind.config.js. Components use token names only." This expectation was
    // never updated and had been failing on main.
    expect(link.className).toContain("bg-role-teacher-nav-active");
    expect(link.className).toContain("text-brand-gold-dark");
    expect(link.className).toContain("font-bold");
  });

  it("applies green stripe class when active for school-admin variant", () => {
    render(
      <NavItem
        label="Overview"
        href="/school/overview"
        icon={Home}
        isActive={true}
        variant="school-admin"
      />,
    );

    const link = screen.getByRole("link", { name: /overview/i });
    expect(link.className).toContain("border-l-[3px]");
    expect(link.className).toContain("border-brand-primary");
    expect(link.className).toContain("bg-brand-light");
    expect(link.className).toContain("text-brand-primary");
  });

  it("applies gray fill class when active for admin variant", () => {
    render(
      <NavItem
        label="Overview"
        href="/kaihle-admin/dashboard"
        icon={Home}
        isActive={true}
        variant="admin"
      />,
    );

    const link = screen.getByRole("link", { name: /overview/i });
    expect(link.className).toContain("bg-gray-100");
    expect(link.className).toContain("text-role-admin-ink");
  });

  it("applies aria-current when active", () => {
    render(
      <NavItem
        label="Dashboard"
        href="/teacher/dashboard"
        isActive={true}
        variant="teacher"
      />,
    );

    expect(screen.getByRole("link")).toHaveAttribute("aria-current", "page");
  });

  it("does not apply aria-current when inactive", () => {
    render(
      <NavItem
        label="Dashboard"
        href="/teacher/dashboard"
        isActive={false}
        variant="teacher"
      />,
    );

    expect(screen.getByRole("link")).not.toHaveAttribute("aria-current");
  });

  it("test_NavItem_when_badge_prop_positive_then_renders_badge_count", () => {
    render(
      <NavItem
        label="Content Review"
        href="/teacher/content-review"
        isActive={false}
        variant="teacher"
        badge={3}
      />,
    );

    expect(screen.getByLabelText("3 pending")).toHaveTextContent("3");
  });

  it("test_NavItem_when_badge_prop_zero_then_renders_no_badge", () => {
    render(
      <NavItem
        label="Content Review"
        href="/teacher/content-review"
        isActive={false}
        variant="teacher"
        badge={0}
      />,
    );

    expect(screen.queryByLabelText(/pending/)).not.toBeInTheDocument();
  });

  it("test_NavItem_when_no_badge_prop_then_renders_no_badge", () => {
    render(
      <NavItem
        label="Content Review"
        href="/teacher/content-review"
        isActive={false}
        variant="teacher"
      />,
    );

    expect(screen.queryByLabelText(/pending/)).not.toBeInTheDocument();
  });
});
