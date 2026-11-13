// Modal: accessible dialog rendered in a portal on document.body.
//   {open && <Modal title="Leave a review" onClose={close} footer={<button ...>}>...</Modal>}
// - `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` pointing at the title.
// - Escape calls `onClose`; Tab and Shift+Tab stay inside the dialog.
// - On mount, focus moves to the first control in the body or footer (or the close button);
//   on unmount, focus returns to the element that had it before the dialog opened.
// The component only exists while mounted, so parents show and hide it with conditional rendering.
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  'input:not([disabled]):not([type="hidden"])',
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export default function Modal({ title, onClose, children, footer }) {
  const titleId = useId();
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);
  const onCloseRef = useRef(onClose);
  // Read before the first commit, so it is the element that opened the dialog.
  const [opener] = useState(() => document.activeElement);

  // Keep the latest onClose without re-subscribing the keydown listener on every render.
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    const getFocusable = () => Array.from(dialog.querySelectorAll(FOCUSABLE_SELECTOR));

    const initialTarget = getFocusable().find((el) => el !== closeButtonRef.current) ?? closeButtonRef.current;
    (initialTarget ?? dialog).focus();

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current?.();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = getFocusable();
      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (!dialog.contains(active)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && (active === first || active === dialog)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (opener?.isConnected && typeof opener.focus === "function") opener.focus();
    };
  }, [opener]);

  return createPortal(
    <div className="modal-backdrop">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        ref={dialogRef}
      >
        <div className="modal-header">
          <h2 id={titleId} className="modal-title">
            {title}
          </h2>
          <button
            type="button"
            className="modal-close"
            aria-label="Close dialog"
            ref={closeButtonRef}
            onClick={() => onClose?.()}
          >
            <span aria-hidden="true">&times;</span>
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>,
    document.body
  );
}
