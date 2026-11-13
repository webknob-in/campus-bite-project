import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

// Toolchain smoke test: jsdom + React Testing Library + jest-dom matchers are wired up.
describe("frontend test setup", () => {
  it("renders React components into the jsdom document with jest-dom matchers", () => {
    render(<button disabled>Place order</button>);

    const button = screen.getByRole("button", { name: "Place order" });
    expect(button).toBeInTheDocument();
    expect(button).toBeDisabled();
  });

  it("provides a working localStorage for the Auth and Cart contexts", () => {
    localStorage.setItem("campusbite_token", "abc");
    expect(localStorage.getItem("campusbite_token")).toBe("abc");
    localStorage.clear();
    expect(localStorage.getItem("campusbite_token")).toBeNull();
  });
});
