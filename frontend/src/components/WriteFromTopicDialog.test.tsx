import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WriteFromTopicDialog } from "./WriteFromTopicDialog";

const mockRequest = vi.fn();
vi.mock("../lib/useApi", () => ({
  useApi: () => ({ request: mockRequest, orgCode: "", authReady: true }),
}));

vi.mock("../i18n", () => ({
  useT: () => ({
    discovery: {
      topic: { loading: "Loading", error: "Error" },
      dialog: {
        title: "Write from topic",
        topicLabel: "Topic",
        instructionsLabel: "Hints",
        instructionsPlaceholder: "Focus on...",
        sourcesLabel: "Sources",
        copyTitle: "Copy",
        addUrl: "Add URL",
        addUrlPlaceholder: "https://...",
        removeUrl: "Remove",
        cancel: "Cancel",
        submit: "Generate",
        submitting: "Generating",
      },
    },
  }),
}));

const detail = {
  id: "t1",
  title: "Topic A",
  blurb: "Blurb",
  categories: ["Polityka"],
  status: "open" as const,
  consumed_at: null,
  consumed_article_id: null,
  last_activity_at: "2026-05-07T10:00:00Z",
  first_seen_at: "2026-05-07T08:00:00Z",
  new_items_since_consume: 0,
  item_count: 1,
  feed_hosts: ["x.com"],
  topic_image_url: null,
  items: [
    {
      id: "i1",
      canonical_url: "https://x.com/a",
      title: "Source A",
      summary: null,
      image_url: null,
      categories: [],
      topic_id: "t1",
      fetched_at: null,
      published_at: null,
    },
  ],
};

beforeEach(() => {
  mockRequest.mockReset();
});

describe("WriteFromTopicDialog", () => {
  it("submits with selected URLs and calls onSubmitted with article_id", async () => {
    mockRequest
      .mockResolvedValueOnce(detail) // GET /discovery/topics/:id
      .mockResolvedValueOnce({ article_id: "a1" }); // POST write_article

    const onSubmitted = vi.fn();
    render(<WriteFromTopicDialog topicId="t1" onCancel={() => {}} onSubmitted={onSubmitted} />);

    await waitFor(() => expect(screen.getByDisplayValue("Topic A")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Generate/ }));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith("a1"));
    const submitCall = mockRequest.mock.calls[1];
    expect(submitCall[0]).toBe("/v2/discovery/topics/t1/write_article");
    expect(submitCall[1].method).toBe("POST");
    const body = JSON.parse(submitCall[1].body);
    expect(body.urls).toEqual(["https://x.com/a"]);
  });

  it("rejects non-http custom URLs silently", async () => {
    mockRequest.mockResolvedValueOnce(detail);
    render(<WriteFromTopicDialog topicId="t1" onCancel={() => {}} onSubmitted={() => {}} />);
    await waitFor(() => expect(screen.getByDisplayValue("Topic A")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("https://...");
    await userEvent.type(input, "javascript:alert(1)");
    await userEvent.click(screen.getByRole("button", { name: /Add URL/ }));

    expect(screen.queryByText(/javascript:/)).toBeNull();
  });

  it("surfaces submit errors in a banner", async () => {
    mockRequest
      .mockResolvedValueOnce(detail)
      .mockRejectedValueOnce(new Error("500: server boom"));
    render(<WriteFromTopicDialog topicId="t1" onCancel={() => {}} onSubmitted={() => {}} />);
    await waitFor(() => expect(screen.getByDisplayValue("Topic A")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /Generate/ }));
    await waitFor(() => expect(screen.getByText(/server boom/)).toBeInTheDocument());
  });
});
