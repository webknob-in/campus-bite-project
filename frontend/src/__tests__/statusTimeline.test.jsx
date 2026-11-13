import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import StatusTimeline from "../components/StatusTimeline";
import { LIFECYCLE } from "../utils/orderStatus";

// Requirements 12.4, 12.5.

describe("StatusTimeline", () => {
  it.each(LIFECYCLE.map((s, i) => [s, i]))("%s marks completed, current and upcoming steps", (status, idx) => {
    const { container } = render(<StatusTimeline status={status} />);
    const steps = [...container.querySelectorAll("li[data-step]")];
    expect(steps.map((s) => s.dataset.step)).toEqual(LIFECYCLE);
    steps.forEach((el, i) => {
      const expected = i < idx ? "completed" : i === idx ? "current" : "upcoming";
      expect(el.dataset.state).toBe(expected);
      if (i === idx) expect(el).toHaveAttribute("aria-current", "step");
      else expect(el).not.toHaveAttribute("aria-current");
    });
    expect(container.querySelectorAll('[aria-current="step"]')).toHaveLength(1);
  });

  it.each([
    ["CANCELLED", /cancelled/i],
    ["REFUNDED", /refunded/i],
  ])("%s shows a terminal banner and no steps", (status, text) => {
    const { container } = render(<StatusTimeline status={status} />);
    expect(screen.getByRole("status")).toHaveTextContent(text);
    expect(container.querySelectorAll("li")).toHaveLength(0);
    expect(container.querySelector('[aria-current="step"]')).toBeNull();
  });
});
