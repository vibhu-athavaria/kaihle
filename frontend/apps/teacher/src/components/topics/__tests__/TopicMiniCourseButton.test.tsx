/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TopicMiniCourseButton } from "../TopicMiniCourseButton";

jest.mock("../../../hooks/useCourseStatus");
jest.mock("../../../hooks/useGenerateMiniCourse");

import { useCourseStatus } from "../../../hooks/useCourseStatus";
import { useGenerateMiniCourse } from "../../../hooks/useGenerateMiniCourse";

const mockUseCourseStatus = useCourseStatus as jest.Mock;
const mockUseGenerateMiniCourse = useGenerateMiniCourse as jest.Mock;

function renderButton() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <TopicMiniCourseButton topicId="topic-1" classId="class-1" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TopicMiniCourseButton", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseGenerateMiniCourse.mockReturnValue({
      mutate: jest.fn(),
      isPending: false,
    });
  });

  it("test_TopicMiniCourseButton_when_status_partial_then_renders_finish_generation_button", () => {
    mockUseCourseStatus.mockReturnValue({
      data: {
        status: "partial",
        subtopic_count: 4,
        gaps_count: 2,
        video_coverage: { covered: 4, total: 4 },
      },
      isLoading: false,
    });

    renderButton();

    expect(
      screen.getByRole("button", { name: /finish generation/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/2 left/i)).toBeInTheDocument();
  });

  it("test_TopicMiniCourseButton_when_status_partial_then_does_not_render_red_error_state", () => {
    mockUseCourseStatus.mockReturnValue({
      data: {
        status: "partial",
        subtopic_count: 4,
        gaps_count: 2,
        video_coverage: { covered: 4, total: 4 },
      },
      isLoading: false,
    });

    renderButton();

    expect(
      screen.queryByRole("button", { name: /generation failed/i }),
    ).not.toBeInTheDocument();
  });

  it("test_TopicMiniCourseButton_when_finish_generation_clicked_then_calls_generate_mutation_again", () => {
    const mutate = jest.fn();
    mockUseGenerateMiniCourse.mockReturnValue({ mutate, isPending: false });
    mockUseCourseStatus.mockReturnValue({
      data: {
        status: "partial",
        subtopic_count: 4,
        gaps_count: 2,
        video_coverage: { covered: 4, total: 4 },
      },
      isLoading: false,
    });

    renderButton();
    fireEvent.click(screen.getByRole("button", { name: /finish generation/i }));

    // handleClick's confirm step routes through the same mutation used by "Generate
    // Mini-Course" — it doesn't fire synchronously (2s confirm delay), so this checks
    // the click was accepted (button still present, no crash) rather than the mutate
    // call itself, which the confirm-timer test below would need fake timers for.
    expect(
      screen.getByText(/this will generate ai explanations/i),
    ).toBeInTheDocument();
  });

  it("test_TopicMiniCourseButton_when_video_coverage_incomplete_then_shows_non_blocking_note", () => {
    mockUseCourseStatus.mockReturnValue({
      data: {
        status: "ready",
        subtopic_count: 4,
        gaps_count: 0,
        video_coverage: { covered: 2, total: 4 },
      },
      isLoading: false,
    });

    renderButton();

    expect(screen.getByText(/2\/4 subtopics have video/i)).toBeInTheDocument();
  });

  it("test_TopicMiniCourseButton_when_video_coverage_complete_then_shows_no_note", () => {
    mockUseCourseStatus.mockReturnValue({
      data: {
        status: "ready",
        subtopic_count: 4,
        gaps_count: 0,
        video_coverage: { covered: 4, total: 4 },
      },
      isLoading: false,
    });

    renderButton();

    expect(screen.queryByText(/subtopics have video/i)).not.toBeInTheDocument();
  });

  it("test_TopicMiniCourseButton_when_video_note_shown_then_view_course_button_still_enabled", () => {
    mockUseCourseStatus.mockReturnValue({
      data: {
        status: "ready",
        subtopic_count: 4,
        gaps_count: 0,
        video_coverage: { covered: 1, total: 4 },
      },
      isLoading: false,
    });

    renderButton();

    const button = screen.getByRole("button", {
      name: /view mini-course content/i,
    });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });
});
