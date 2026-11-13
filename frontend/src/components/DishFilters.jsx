// DishFilters: name search plus minimum and maximum price inputs (Requirement 9.7).
// Controlled by the page: `values` is `{search, min, max}`, `errors` is `{min?, max?}`, and
// `onChange` receives the input change event (input names are `search`, `min`, `max`).
import FormField from "./FormField.jsx";
import "../styles/pages/BrowseCards.css";

export default function DishFilters({ values, errors = {}, onChange, searchLabel = "Search dishes" }) {
  return (
    <form className="dish-filters" role="search" onSubmit={(event) => event.preventDefault()} noValidate>
      <FormField
        label={searchLabel}
        name="search"
        type="search"
        value={values.search}
        onChange={onChange}
        placeholder="Dish name"
        className="dish-filters-search"
      />
      <FormField
        label="Min price"
        name="min"
        type="number"
        inputMode="decimal"
        min="0"
        step="0.01"
        value={values.min}
        onChange={onChange}
        error={errors.min}
      />
      <FormField
        label="Max price"
        name="max"
        type="number"
        inputMode="decimal"
        min="0"
        step="0.01"
        value={values.max}
        onChange={onChange}
        error={errors.max}
      />
    </form>
  );
}
