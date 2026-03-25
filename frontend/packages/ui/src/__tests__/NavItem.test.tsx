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
    expect(link.className).toContain("bg-[#fffbeb]");
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
        href="/kaihle-admin/overview"
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
});
