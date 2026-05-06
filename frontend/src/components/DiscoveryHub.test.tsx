import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DiscoveryHub } from "./DiscoveryHub";

vi.mock("../lib/useApi", () => ({
  useApi: () => ({ request: vi.fn(async () => ({})), orgCode: "", authReady: true }),
}));
vi.mock("../lib/useDiscoveryFeeds", () => ({
  useDiscoveryFeeds: () => ({ feeds: [], loading: false }),
}));
vi.mock("../lib/useDiscoveryTopics", () => ({
  useDiscoveryTopics: () => ({ topics: [], loading: false }),
}));
vi.mock("../lib/useDiscoveryItems", () => ({
  useDiscoveryItems: () => ({ items: [], loading: false }),
}));

describe("DiscoveryHub", () => {
  it("renders the three view tabs", () => {
    render(<DiscoveryHub />);
    expect(screen.getByRole("button", { name: /Tematy/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Itemy/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Feedy/ })).toBeInTheDocument();
  });
});
