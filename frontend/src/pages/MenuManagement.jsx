// Menu management for restaurant owners (Requirement 16.8).
// Searchable, paginated dish table with create/edit modal, delete confirmation and an
// availability switch. Backend errors show inline.
import { useEffect, useState } from "react";
import {
  createMenuItem,
  deleteMenuItem,
  listOwnerMenuItems,
  setMenuItemAvailability,
  updateMenuItem,
} from "../api/owner.js";
import { getErrorMessage } from "../api/client.js";
import useAsync from "../hooks/useAsync.js";
import useDebouncedValue from "../hooks/useDebouncedValue.js";
import Modal from "../components/Modal.jsx";
import FormField from "../components/FormField.jsx";
import Loader from "../components/Loader.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Pagination from "../components/Pagination.jsx";
import { formatCurrency } from "../utils/format.js";
import "../styles/pages/MenuManagement.css";

const PAGE_SIZE = 10;
const EMPTY_FORM = { name: "", description: "", category: "", price: "", image_url: "", is_available: true };

/** Mirrors backend rules; returns {field: message}. */
export function validateMenuForm(form) {
  const errors = {};
  const name = form.name.trim();
  if (!name) errors.name = "Name is required.";
  else if (name.length > 120) errors.name = "Name must be at most 120 characters.";
  const price = String(form.price).trim();
  if (!/^\d+(\.\d{1,2})?$/.test(price)) {
    errors.price = "Enter a price with at most 2 decimal places.";
  } else if (!(Number(price) > 0)) {
    errors.price = "Price must be greater than 0.";
  } else if (Number(price) > 100000) {
    errors.price = "Price must be at most 100000.";
  }
  return errors;
}

function Thumb({ url, name, className = "menu-thumb" }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  return (
    <div className={className} aria-hidden="true">
      {url && !failed ? (
        <img src={url} alt="" loading="lazy" onError={() => setFailed(true)} />
      ) : (
        <div className="menu-thumb-fallback">{name?.trim()?.charAt(0)?.toUpperCase() || "?"}</div>
      )}
    </div>
  );
}

function MenuItemForm({ item, onClose, onSaved }) {
  const [form, setForm] = useState(
    item
      ? {
          name: item.name ?? "",
          description: item.description ?? "",
          category: item.category ?? "",
          price: item.price ?? "",
          image_url: item.image_url ?? "",
          is_available: item.is_available ?? true,
        }
      : EMPTY_FORM
  );
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const [serverError, setServerError] = useState(null);
  const errors = validateMenuForm(form);
  const shown = submitted ? errors : {};
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitted(true);
    if (Object.keys(errors).length > 0 || pending) return;
    const body = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      category: form.category.trim() || null,
      price: Number(form.price.trim()).toFixed(2),
      image_url: form.image_url.trim() || null,
      is_available: form.is_available,
    };
    setPending(true);
    setServerError(null);
    try {
      if (item) await updateMenuItem(item.id, body);
      else await createMenuItem(body);
      onSaved();
    } catch (err) {
      setServerError(getErrorMessage(err));
      setPending(false);
    }
  }

  return (
    <Modal
      title={item ? "Edit menu item" : "Add menu item"}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button
            type="submit"
            form="menu-item-form"
            className="btn btn-primary"
            disabled={pending || (submitted && Object.keys(errors).length > 0)}
          >
            {pending ? "Saving..." : "Save"}
          </button>
        </>
      }
    >
      <form id="menu-item-form" onSubmit={handleSubmit} noValidate>
        {serverError && <ErrorMessage message={serverError} />}
        <FormField label="Name" value={form.name} onChange={set("name")} error={shown.name} required maxLength={200} />
        <FormField
          label="Price"
          inputMode="decimal"
          value={form.price}
          onChange={set("price")}
          error={shown.price}
          required
        />
        <FormField label="Category" value={form.category} onChange={set("category")} />
        <FormField label="Description" as="textarea" rows={3} value={form.description} onChange={set("description")} />
        <FormField label="Image URL" value={form.image_url} onChange={set("image_url")} />
        {form.image_url.trim() && <Thumb url={form.image_url.trim()} name={form.name} className="menu-image-preview" />}
        <label className="menu-available-check">
          <input
            type="checkbox"
            checked={form.is_available}
            onChange={(e) => setForm({ ...form, is_available: e.target.checked })}
          />{" "}
          Available
        </label>
      </form>
    </Modal>
  );
}

function DeleteConfirm({ item, onClose, onDeleted }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  async function confirm() {
    setPending(true);
    setError(null);
    try {
      await deleteMenuItem(item.id);
      onDeleted();
    } catch (err) {
      setError(getErrorMessage(err));
      setPending(false);
    }
  }
  return (
    <Modal
      title="Delete menu item"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button type="button" className="btn btn-danger" onClick={confirm} disabled={pending}>
            {pending ? "Deleting..." : "Delete"}
          </button>
        </>
      }
    >
      {error && <ErrorMessage message={error} />}
      <p>Delete "{item.name}"? This cannot be undone.</p>
    </Modal>
  );
}

export default function MenuManagement() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null); // null | {} (new) | item
  const [deleting, setDeleting] = useState(null);
  const [rowState, setRowState] = useState({}); // id -> {pending, error}
  const debounced = useDebouncedValue(search.trim(), 300);

  const { data, loading, error, reload } = useAsync(
    () => listOwnerMenuItems({ search: debounced || undefined, page, page_size: PAGE_SIZE }),
    [debounced, page]
  );

  function handleSearch(e) {
    setSearch(e.target.value);
    setPage(1);
  }

  async function toggle(item) {
    setRowState((s) => ({ ...s, [item.id]: { pending: true, error: null } }));
    try {
      await setMenuItemAvailability(item.id, !item.is_available);
      setRowState((s) => ({ ...s, [item.id]: { pending: false, error: null } }));
      reload();
    } catch (err) {
      setRowState((s) => ({ ...s, [item.id]: { pending: false, error: getErrorMessage(err) } }));
    }
  }

  function afterDelete() {
    const remaining = (data?.items?.length ?? 1) - 1;
    setDeleting(null);
    if (remaining <= 0 && page > 1) setPage(page - 1);
    else reload();
  }

  const items = data?.items ?? [];

  return (
    <section className="menu-management">
      <div className="menu-management-header">
        <h1>Menu management</h1>
        <button type="button" className="btn btn-primary" onClick={() => setEditing({})}>
          Add item
        </button>
      </div>
      <FormField
        label="Search dishes"
        type="search"
        value={search}
        onChange={handleSearch}
        placeholder="Search by name"
      />
      {loading && <Loader />}
      {!loading && error && <ErrorMessage message={error} onRetry={reload} />}
      {!loading && !error && data && (
        <>
          {items.length === 0 ? (
            <p className="menu-empty">No menu items found.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th className="menu-thumb-cell"><span className="visually-hidden">Image</span></th>
                    <th>Name</th>
                    <th>Price</th>
                    <th>Available</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const rs = rowState[item.id] ?? {};
                    return (
                      <tr key={item.id}>
                        <td className="menu-thumb-cell">
                          <Thumb url={item.image_url} name={item.name} />
                        </td>
                        <td>{item.name}</td>
                        <td>{formatCurrency(item.price)}</td>
                        <td>
                          <button
                            type="button"
                            role="switch"
                            className={`menu-switch${item.is_available ? " is-on" : ""}`}
                            aria-checked={item.is_available}
                            aria-label={`${item.name} available`}
                            disabled={rs.pending}
                            onClick={() => toggle(item)}
                          >
                            <span className="menu-switch-knob" aria-hidden="true" />
                          </button>
                          {rs.error && (
                            <p className="field-error" role="alert">
                              {rs.error}
                            </p>
                          )}
                        </td>
                        <td className="menu-actions">
                          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing(item)}>
                            Edit
                          </button>
                          <button type="button" className="btn btn-danger btn-sm" onClick={() => setDeleting(item)}>
                            Delete
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
        </>
      )}
      {editing && (
        <MenuItemForm
          item={editing.id != null ? editing : null}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
      {deleting && <DeleteConfirm item={deleting} onClose={() => setDeleting(null)} onDeleted={afterDelete} />}
    </section>
  );
}
