import { render, screen } from "@testing-library/react";
import { Sidebar } from "../components/nav/Sidebar";

describe("Sidebar", () => {
  it("test_Sidebar_when_teacher_variant_then_renders_content_review_nav_item", () => {
    render(<Sidebar variant="teacher" />);
    expect(
      screen.getByRole("link", { name: /content review/i }),
    ).toHaveAttribute("href", "/teacher/content-review");
  });

  it("test_Sidebar_when_teacher_variant_and_pending_count_then_renders_badge", () => {
    render(<Sidebar variant="teacher" contentReviewPendingCount={5} />);
    expect(screen.getByLabelText("5 pending")).toHaveTextContent("5");
  });

  it("test_Sidebar_when_teacher_variant_and_no_pending_count_then_renders_no_badge", () => {
    render(<Sidebar variant="teacher" />);
    expect(screen.queryByLabelText(/pending/)).not.toBeInTheDocument();
  });

  it("test_Sidebar_when_admin_variant_then_renders_video_review_and_course_content_review_labels", () => {
    render(<Sidebar variant="admin" />);
    // Regression guard: these two nav items were both once labeled "Content Review",
    // which collided with each other and was the source of real user confusion (MCR-T2).
    expect(screen.getByRole("link", { name: /video review/i })).toHaveAttribute(
      "href",
      "/kaihle-admin/content/review",
    );
    expect(
      screen.getByRole("link", { name: /course content review/i }),
    ).toHaveAttribute("href", "/kaihle-admin/content/promotion");
    // Neither of the old, colliding labels should appear standalone anymore.
    expect(
      screen.queryByRole("link", { name: /^content review$/i }),
    ).not.toBeInTheDocument();
  });
});
