import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ErrorMessage from "../components/ErrorMessage.jsx";
import FormField from "../components/FormField.jsx";
import Loader from "../components/Loader.jsx";
import Modal from "../components/Modal.jsx";
import Pagination from "../components/Pagination.jsx";
import StatusBadge, { statusLabel, statusTone } from "../components/StatusBadge.jsx";

describe("Loader", () => {
  it("announces a polite status with the default and a custom label", () => {
    const { rerender } = render(<Loader />);
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Loading...");
    expect(status).toHaveAttribute("aria-live", "polite");

    rerender(<Loader label="Loading orders..." />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading orders...");
  });
});

describe("ErrorMessage", () => {
  it("shows the message as an alert and calls onRetry from the retry button", async () => {
    const onRetry = vi.fn();
    render(<ErrorMessage message="Restaurant not found" onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Restaurant not found");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("omits the retry button without onRetry and falls back to a generic message", () => {
    render(<ErrorMessage />);

    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("Pagination", () => {
  it("shows 'Page X of Y' and moves to the previous and next page", async () => {
    const onPageChange = vi.fn();
    render(<Pagination page={2} pageSize={10} total={45} onPageChange={onPageChange} />);

    expect(screen.getByText("Page 2 of 5")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onPageChange).toHaveBeenLastCalledWith(3);
    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(onPageChange).toHaveBeenLastCalledWith(1);
  });

  it("disables Previous on the first page and Next on the last page", () => {
    const { rerender } = render(<Pagination page={1} pageSize={10} total={45} onPageChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();

    rerender(<Pagination page={5} pageSize={10} total={45} onPageChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("renders 'Page 1 of 1' with both controls disabled when there are no records", () => {
    render(<Pagination page={1} pageSize={10} total={0} onPageChange={() => {}} />);

    expect(screen.getByText("Page 1 of 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("steps back to the last real page when the current page is past the end", async () => {
    const onPageChange = vi.fn();
    render(<Pagination page={9} pageSize={10} total={25} onPageChange={onPageChange} />);

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });
});

describe("StatusBadge", () => {
  it("renders Order_Status, Payment_Status, and Return_Status with readable labels and tones", () => {
    render(
      <>
        <StatusBadge status="OUT_FOR_DELIVERY" />
        <StatusBadge status="mock_paid" type="payment" />
        <StatusBadge status="requested" />
        <StatusBadge status="none" type="return" />
      </>
    );

    expect(screen.getByText("Out for delivery")).toHaveClass("badge", "badge-transit");
    expect(screen.getByText("Mock paid")).toHaveClass("badge-success");
    expect(screen.getByText("Requested")).toHaveClass("badge-progress");
    expect(screen.getByText("No return")).toHaveClass("badge-neutral");
  });

  it("maps every status value from the glossary to a tone", () => {
    const orderTones = {
      PLACED: "info",
      ACCEPTED: "info",
      PREPARING: "progress",
      READY: "progress",
      ASSIGNED: "transit",
      OUT_FOR_DELIVERY: "transit",
      DELIVERED: "success",
      CANCELLED: "danger",
      REFUNDED: "neutral",
    };
    for (const [status, tone] of Object.entries(orderTones)) {
      expect(statusTone(status, "order")).toBe(tone);
    }
    expect(statusTone("pending", "payment")).toBe("progress");
    expect(statusTone("refunded", "payment")).toBe("neutral");
    expect(statusTone("approved", "return")).toBe("success");
    expect(statusTone("rejected", "return")).toBe("danger");
  });

  it("tells Order_Status REFUNDED apart from Payment_Status refunded and handles unknown values", () => {
    expect(statusLabel("REFUNDED")).toBe("Refunded");
    expect(statusLabel("refunded")).toBe("Refunded");
    expect(statusTone("SOMETHING_NEW")).toBe("neutral");

    const { container, rerender } = render(<StatusBadge status="SOMETHING_NEW" />);
    expect(screen.getByText("Something new")).toHaveClass("badge-neutral");

    rerender(<StatusBadge status={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("FormField", () => {
  it("associates the label with the control", async () => {
    const onChange = vi.fn();
    render(<FormField label="Email" type="email" value="" onChange={onChange} />);

    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("type", "email");
    await userEvent.type(input, "a");
    expect(onChange).toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("shows an inline error linked to the control", () => {
    render(<FormField label="Password" type="password" defaultValue="" error="Password must be at least 8 characters" />);

    const input = screen.getByLabelText("Password");
    const error = screen.getByRole("alert");
    expect(error).toHaveTextContent("Password must be at least 8 characters");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toContain(error.id);
    expect(input.closest(".form-field")).toHaveClass("has-error");
  });

  it("renders textarea and select controls and forwards props such as disabled", () => {
    render(
      <>
        <FormField label="Comment" as="textarea" defaultValue="" maxLength={1000} />
        <FormField label="Status" as="select" defaultValue="PLACED" disabled>
          <option value="PLACED">Placed</option>
          <option value="READY">Ready</option>
        </FormField>
      </>
    );

    expect(screen.getByLabelText("Comment").tagName).toBe("TEXTAREA");
    expect(screen.getByLabelText("Comment")).toHaveAttribute("maxlength", "1000");
    const select = screen.getByLabelText("Status");
    expect(select.tagName).toBe("SELECT");
    expect(select).toBeDisabled();
    expect(screen.getByRole("option", { name: "Ready" })).toBeInTheDocument();
  });
});

describe("Modal", () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          Open review
        </button>
        {open && (
          <Modal title="Leave a review" onClose={() => setOpen(false)}>
            <button type="button">First</button>
            <button type="button">Last</button>
          </Modal>
        )}
      </>
    );
  }

  it("renders an accessible dialog named by its title with the body and footer", () => {
    render(
      <Modal title="Delete dish" onClose={() => {}} footer={<button type="button">Confirm</button>}>
        <p>Are you sure?</p>
      </Modal>
    );

    const dialog = screen.getByRole("dialog", { name: "Delete dish" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveTextContent("Are you sure?");
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });

  it("closes on Escape and from the close button", async () => {
    const onClose = vi.fn();
    render(
      <Modal title="Return request" onClose={onClose}>
        <p>Body</p>
      </Modal>
    );

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Close dialog" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("moves focus into the dialog, keeps Tab inside it, and restores focus on close", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const opener = screen.getByRole("button", { name: "Open review" });
    await user.click(opener);
    expect(screen.getByRole("button", { name: "First" })).toHaveFocus();

    await user.tab();
    expect(screen.getByRole("button", { name: "Last" })).toHaveFocus();
    await user.tab(); // wraps from the last control to the first (the close button)
    expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus();
    await user.tab({ shift: true }); // wraps back to the last control
    expect(screen.getByRole("button", { name: "Last" })).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
