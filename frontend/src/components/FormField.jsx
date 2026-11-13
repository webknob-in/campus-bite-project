// FormField: label, control, optional hint, and inline error message (Requirement 33.5).
//   <FormField label="Email" type="email" value={email} onChange={...} error={errors.email} required />
//   <FormField label="Comment" as="textarea" ... />
//   <FormField label="Status" as="select" ...><option>...</option></FormField>
// Every other prop (type, name, value, onChange, disabled, maxLength, ...) goes to the control.
// The error is linked to the control with `aria-describedby` and `aria-invalid`.
import { useId } from "react";

export default function FormField({
  label,
  id,
  as: Control = "input",
  error,
  hint,
  required,
  className = "",
  children,
  ...controlProps
}) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const hintId = hint ? `${fieldId}-hint` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  const classes = ["form-field", error ? "has-error" : "", className].filter(Boolean).join(" ");

  return (
    <div className={classes}>
      <label htmlFor={fieldId}>
        {label}
        {required && (
          <span className="required-mark" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>
      <Control
        id={fieldId}
        required={required}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        {...controlProps}
      >
        {children}
      </Control>
      {hint && (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
