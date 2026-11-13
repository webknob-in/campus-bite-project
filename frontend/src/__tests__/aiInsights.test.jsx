import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { askInsight, getInsightSummary } from "../api/ai.js";
import AIInsights from "../pages/AIInsights";

// Requirements 29.9 (and 28.6, 28.9).

vi.mock("../api/ai.js", () => ({ askInsight: vi.fn(), getInsightSummary: vi.fn() }));

const axiosError = (status, headers = {}) => ({ isAxiosError: true, response: { status, headers, data: {} } });

beforeEach(() => vi.clearAllMocks());

describe("AIInsights", () => {
  it("shows the rate-limit message with Retry-After seconds on 429", async () => {
    askInsight.mockRejectedValue(axiosError(429, { "retry-after": "42" }));
    render(<AIInsights />);
    await userEvent.click(screen.getByRole("button", { name: "How much did I spend this week?" }));
    expect(await screen.findByText(/Too many requests.*42 seconds/)).toBeInTheDocument();
  });

  it("shows the 502 and 503 messages", async () => {
    askInsight.mockRejectedValueOnce(axiosError(502));
    render(<AIInsights />);
    const btn = screen.getByRole("button", { name: "How much did I spend this week?" });
    await userEvent.click(btn);
    expect(await screen.findByText(/AI service is temporarily unavailable/)).toBeInTheDocument();
    askInsight.mockRejectedValueOnce(axiosError(503));
    await userEvent.click(btn);
    expect(await screen.findByText(/not configured/)).toBeInTheDocument();
  });

  it("shows the answer on success and sends the exact preset string", async () => {
    askInsight.mockResolvedValue({ answer: "You spent 120 this week.", order_count: 3, generated_at: "2024-01-01T00:00:00Z" });
    render(<AIInsights />);
    await userEvent.click(screen.getByRole("button", { name: "Which of my orders are still not delivered?" }));
    expect(await screen.findByText("You spent 120 this week.")).toBeInTheDocument();
    expect(askInsight).toHaveBeenCalledWith("Which of my orders are still not delivered?");
  });

  it("sends every preset string unchanged", async () => {
    askInsight.mockResolvedValue({ answer: "ok", order_count: 0, generated_at: "2024-01-01T00:00:00Z" });
    render(<AIInsights />);
    for (const text of [
      "Summarize my last five orders.",
      "How much did I spend this week?",
      "Which food items have I ordered most frequently?",
    ]) {
      await userEvent.click(screen.getByRole("button", { name: text }));
      await screen.findByText("ok");
      expect(askInsight).toHaveBeenLastCalledWith(text);
    }
  });

  it("summary button calls getInsightSummary", async () => {
    getInsightSummary.mockResolvedValue({ answer: "Summary text", order_count: 5, generated_at: "2024-01-01T00:00:00Z" });
    render(<AIInsights />);
    await userEvent.click(screen.getByRole("button", { name: "Summarize my last 5 orders" }));
    expect(await screen.findByText("Summary text")).toBeInTheDocument();
  });
});
