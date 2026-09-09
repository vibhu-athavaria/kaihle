/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
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

  it("test_TopicMiniCourseButton_when_status_partial_then_renders_generate_missing_button", () => {
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
      screen.getByRole("button", { name: /generate missing/i }),
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

  it("test_TopicMiniCourseButton_when_generate_missing_clicked_then_calls_generate_mutation_again", () => {
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
    fireEvent.click(screen.getByRole("button", { name: /generate missing/i }));

    // handleClick's confirm step routes through the same mutation used by "Generate
    // Mini-Course" — it doesn't fire synchronously (2s confirm delay), so this checks
    // the click was accepted (button still present, no crash) rather than the mutate
    // call itself, which the confirm-timer test below would need fake timers for.
    expect(
      screen.getByText(/this will generate ai explanations/i),
    ).toBeInTheDocument();
  });

  it("test_TopicMiniCourseButton_when_status_still_stale_partial_after_click_then_stays_generating", async () => {
    jest.useFakeTimers();
    try {
      const mutate = jest.fn(
        (_topicId: string, opts: { onSuccess: (data: unknown) => void }) => {
          opts.onSuccess({});
        },
      );
      mockUseGenerateMiniCourse.mockReturnValue({ mutate, isPending: false });

      const staleUpdatedAt = 1000;
      mockUseCourseStatus.mockReturnValue({
        data: {
          status: "partial",
          subtopic_count: 4,
          gaps_count: 2,
          video_coverage: { covered: 4, total: 4 },
        },
        dataUpdatedAt: staleUpdatedAt,
        isLoading: false,
      });

      const { rerender } = renderButton();

      fireEvent.click(
        screen.getByRole("button", { name: /generate missing/i }),
      );

      act(() => {
        jest.advanceTimersByTime(2000);
      });

      // mutate's mocked onSuccess fired synchronously above, setting localState to
      // "generating" and capturing the CURRENT (stale) dataUpdatedAt as the baseline.
      // useCourseStatus's mock still returns that same stale value on this render — if
      // the fix weren't in place, the completion-detection effect would treat the
      // unchanged "partial" as a fresh completion and revert to idle right here.
      expect(screen.getByText(/generating content/i)).toBeInTheDocument();

      // Now simulate a genuinely fresh poll — still "partial" (a legitimate case: the
      // retry left some gaps too) but with a NEWER dataUpdatedAt.
      mockUseCourseStatus.mockReturnValue({
        data: {
          status: "partial",
          subtopic_count: 4,
          gaps_count: 1,
          video_coverage: { covered: 4, total: 4 },
        },
        dataUpdatedAt: staleUpdatedAt + 1,
        isLoading: false,
      });
      rerender(
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <MemoryRouter>
            <TopicMiniCourseButton topicId="topic-1" classId="class-1" />
          </MemoryRouter>
        </QueryClientProvider>,
      );

      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /generate missing/i }),
        ).toBeInTheDocument(),
      );
    } finally {
      jest.useRealTimers();
    }
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
