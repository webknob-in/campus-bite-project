// Dish search page (Requirements 9.7, 33.2, 33.3, 35.2, 35.6).
// Searches dishes across all restaurants by name and price range; each result links to its restaurant.
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { listDishes } from "../api/restaurants.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useCart } from "../context/CartContext.jsx";
import useAsync from "../hooks/useAsync.js";
import useDebouncedValue from "../hooks/useDebouncedValue.js";
import { ROLES } from "../utils/roles.js";
import { isPriceRangeValid, validatePriceRange } from "../utils/money.js";
import DishFilters from "../components/DishFilters.jsx";
import Loader from "../components/Loader.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Pagination from "../components/Pagination.jsx";
import MenuItemCard from "../components/MenuItemCard.jsx";
import "../styles/pages/DishSearch.css";

const PAGE_SIZE = 12;
const FILTER_DELAY_MS = 300;

export default function DishSearch() {
  const { isAuthenticated, role } = useAuth();
  const { addItem } = useCart();
  const navigate = useNavigate();
  const location = useLocation();

  const [filters, setFilters] = useState({ search: "", min: "", max: "" });
  const applied = useDebouncedValue(filters, FILTER_DELAY_MS);

  const liveErrors = validatePriceRange(filters.min, filters.max);
  const appliedValid = isPriceRangeValid(validatePriceRange(applied.min, applied.max));

  const filterKey = JSON.stringify([applied.search.trim(), applied.min.trim(), applied.max.trim()]);
  const [pageState, setPageState] = useState({ key: filterKey, page: 1 });
  const page = pageState.key === filterKey ? pageState.page : 1;

  const { data, loading, error, reload } = useAsync(() => {
    // Invalid price filters are reported inline and never reach the API.
    if (!appliedValid) return null;
    return listDishes({
      search: applied.search.trim(),
      min_price: applied.min.trim(),
      max_price: applied.max.trim(),
      page,
      page_size: PAGE_SIZE,
    });
  }, [filterKey, page]);

  const handleFilterChange = (event) => {
    const { name, value } = event.target;
    setFilters((current) => ({ ...current, [name]: value }));
  };

  // Only visitors and Customers can order; visitors are sent to log in first (Requirement 35.6).
  const canAdd = !isAuthenticated || role === ROLES.CUSTOMER;
  const handleAdd = (dish) => {
    if (!isAuthenticated) {
      navigate("/login", { state: { from: location } });
      return;
    }
    addItem(dish, { id: dish.restaurant_id, name: dish.restaurant_name });
  };

  const items = data?.items ?? [];

  return (
    <main className="container dish-search-page">
      <h1 className="page-title">Find dishes</h1>
      <DishFilters values={filters} errors={liveErrors} onChange={handleFilterChange} />

      {!appliedValid && <p className="text-muted">Fix the price filters to see results.</p>}
      {appliedValid && loading && <Loader label="Searching dishes..." />}
      {appliedValid && !loading && error && <ErrorMessage message={error} onRetry={reload} />}
      {appliedValid && !loading && !error && data && (
        <>
          {items.length === 0 ? (
            <p className="empty-state text-muted">No dishes match your filters.</p>
          ) : (
            <ul className="grid dish-grid">
              {items.map((dish) => (
                <li key={dish.id}>
                  <MenuItemCard item={dish} restaurantLink onAdd={canAdd ? handleAdd : undefined} />
                </li>
              ))}
            </ul>
          )}
          {(data.total > 0 || page > 1) && (
            <Pagination
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              onPageChange={(next) => setPageState({ key: filterKey, page: next })}
            />
          )}
        </>
      )}
    </main>
  );
}
