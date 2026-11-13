// Restaurant list page (Requirements 8.7, 33.2, 33.3, 35.2).
// Debounced name/cuisine search, a card grid, and pagination.
import { useState } from "react";
import { listRestaurants } from "../api/restaurants.js";
import useAsync from "../hooks/useAsync.js";
import useDebouncedValue from "../hooks/useDebouncedValue.js";
import FormField from "../components/FormField.jsx";
import Loader from "../components/Loader.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Pagination from "../components/Pagination.jsx";
import RestaurantCard from "../components/RestaurantCard.jsx";
import "../styles/pages/RestaurantList.css";

const PAGE_SIZE = 12;
const SEARCH_DELAY_MS = 300;

export default function RestaurantList() {
  const [search, setSearch] = useState("");
  const query = useDebouncedValue(search, SEARCH_DELAY_MS).trim();

  // The page number belongs to the query it was chosen for; a new query starts again at page 1.
  const [pageState, setPageState] = useState({ query: "", page: 1 });
  const page = pageState.query === query ? pageState.page : 1;

  const { data, loading, error, reload } = useAsync(
    () => listRestaurants({ search: query, page, page_size: PAGE_SIZE }),
    [query, page]
  );

  const items = data?.items ?? [];

  return (
    <main className="container restaurant-list-page">
      <h1 className="page-title">Restaurants</h1>

      <form className="restaurant-search" role="search" onSubmit={(event) => event.preventDefault()}>
        <FormField
          label="Search by name or cuisine"
          name="search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="e.g. Pizza"
        />
      </form>

      {loading && <Loader label="Loading restaurants..." />}
      {!loading && error && <ErrorMessage message={error} onRetry={reload} />}
      {!loading && !error && data && (
        <>
          {items.length === 0 ? (
            <p className="empty-state text-muted">
              {query ? `No restaurants match "${query}".` : "No restaurants available yet."}
            </p>
          ) : (
            <ul className="grid restaurant-grid">
              {items.map((restaurant) => (
                <li key={restaurant.id}>
                  <RestaurantCard restaurant={restaurant} />
                </li>
              ))}
            </ul>
          )}
          {(data.total > 0 || page > 1) && (
            <Pagination
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              onPageChange={(next) => setPageState({ query, page: next })}
            />
          )}
        </>
      )}
    </main>
  );
}
