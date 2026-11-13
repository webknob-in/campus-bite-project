// Restaurant menu page (Requirements 8.8, 9.7, 33.2, 33.3, 35.2, 35.6).
// Header with rating, name search and price filters, menu card grid, and a paginated reviews list.
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { getRestaurant, getRestaurantMenu, getRestaurantReviews } from "../api/restaurants.js";
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
import RatingSummary from "../components/RatingSummary.jsx";
import "../styles/pages/RestaurantMenu.css";

const MENU_PAGE_SIZE = 12;
const REVIEW_PAGE_SIZE = 5;
const FILTER_DELAY_MS = 300;

function formatReviewDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
}

function ReviewsSection({ restaurantId }) {
  const [pageState, setPageState] = useState({ id: restaurantId, page: 1 });
  const page = pageState.id === restaurantId ? pageState.page : 1;

  const { data, loading, error, reload } = useAsync(
    () => getRestaurantReviews(restaurantId, { page, page_size: REVIEW_PAGE_SIZE }),
    [restaurantId, page]
  );
  const reviews = data?.items ?? [];

  return (
    <section className="reviews-section" aria-labelledby="reviews-title">
      <h2 id="reviews-title">Reviews</h2>
      {loading && <Loader label="Loading reviews..." />}
      {!loading && error && <ErrorMessage message={error} onRetry={reload} />}
      {!loading && !error && data && (
        <>
          {reviews.length === 0 ? (
            <p className="empty-state text-muted">No reviews yet.</p>
          ) : (
            <ul className="review-list">
              {reviews.map((review) => (
                <li key={review.id} className="review-item">
                  <div className="review-heading">
                    <strong>{review.customer_name}</strong>
                    <span className="review-rating" aria-label={`Rated ${review.rating} out of 5`}>
                      <span aria-hidden="true" className="rating-star">
                        {"★".repeat(review.rating)}
                      </span>
                      <span aria-hidden="true" className="review-star-empty">
                        {"★".repeat(Math.max(0, 5 - review.rating))}
                      </span>
                    </span>
                    <span className="text-muted review-date">{formatReviewDate(review.created_at)}</span>
                  </div>
                  {review.comment && <p className="review-comment">{review.comment}</p>}
                </li>
              ))}
            </ul>
          )}
          {(data.total > 0 || page > 1) && (
            <Pagination
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              onPageChange={(next) => setPageState({ id: restaurantId, page: next })}
            />
          )}
        </>
      )}
    </section>
  );
}

export default function RestaurantMenu() {
  const { id } = useParams();
  const { isAuthenticated, role } = useAuth();
  const { addItem } = useCart();
  const navigate = useNavigate();
  const location = useLocation();

  const restaurantState = useAsync(() => getRestaurant(id), [id]);
  const restaurant = restaurantState.data;

  const [filters, setFilters] = useState({ search: "", min: "", max: "" });
  const applied = useDebouncedValue(filters, FILTER_DELAY_MS);

  const liveErrors = validatePriceRange(filters.min, filters.max);
  const appliedValid = isPriceRangeValid(validatePriceRange(applied.min, applied.max));

  const filterKey = JSON.stringify([id, applied.search.trim(), applied.min.trim(), applied.max.trim()]);
  const [pageState, setPageState] = useState({ key: filterKey, page: 1 });
  const page = pageState.key === filterKey ? pageState.page : 1;

  const menuState = useAsync(() => {
    // Invalid price filters are reported inline and never reach the API.
    if (!appliedValid) return null;
    return getRestaurantMenu(id, {
      search: applied.search.trim(),
      min_price: applied.min.trim(),
      max_price: applied.max.trim(),
      page,
      page_size: MENU_PAGE_SIZE,
    });
  }, [filterKey, page]);

  const handleFilterChange = (event) => {
    const { name, value } = event.target;
    setFilters((current) => ({ ...current, [name]: value }));
  };

  // Only visitors and Customers can order; visitors are sent to log in first (Requirement 35.6).
  const canAdd = !isAuthenticated || role === ROLES.CUSTOMER;
  const handleAdd = (item) => {
    if (!isAuthenticated) {
      navigate("/login", { state: { from: location } });
      return;
    }
    addItem(item, { id: restaurant.id, name: restaurant.name });
  };

  if (restaurantState.loading) {
    return (
      <main className="container restaurant-menu-page">
        <Loader label="Loading restaurant..." />
      </main>
    );
  }

  if (restaurantState.error || !restaurant) {
    return (
      <main className="container restaurant-menu-page">
        <ErrorMessage message={restaurantState.error} onRetry={restaurantState.reload} />
        <p className="back-link">
          <Link to="/restaurants">Back to restaurants</Link>
        </p>
      </main>
    );
  }

  const menuItems = menuState.data?.items ?? [];

  return (
    <main className="container restaurant-menu-page">
      <header className="restaurant-header">
        <p className="back-link">
          <Link to="/restaurants">&larr; All restaurants</Link>
        </p>
        <div className="restaurant-header-main">
          <h1>{restaurant.name}</h1>
          <span className={`badge ${restaurant.is_open ? "badge-success" : "badge-neutral"}`}>
            {restaurant.is_open ? "Open" : "Closed"}
          </span>
        </div>
        <p className="restaurant-header-meta">
          <RatingSummary average={restaurant.average_rating} count={restaurant.review_count} />
          <span className="text-muted">{restaurant.cuisine}</span>
        </p>
        {restaurant.description && <p>{restaurant.description}</p>}
        <p className="text-muted">{restaurant.address}</p>
      </header>

      <section aria-labelledby="menu-title">
        <h2 id="menu-title">Menu</h2>
        <DishFilters values={filters} errors={liveErrors} onChange={handleFilterChange} searchLabel="Search menu" />

        {!appliedValid && <p className="text-muted">Fix the price filters to see results.</p>}
        {appliedValid && menuState.loading && <Loader label="Loading menu..." />}
        {appliedValid && !menuState.loading && menuState.error && (
          <ErrorMessage message={menuState.error} onRetry={menuState.reload} />
        )}
        {appliedValid && !menuState.loading && !menuState.error && menuState.data && (
          <>
            {menuItems.length === 0 ? (
              <p className="empty-state text-muted">No menu items match your filters.</p>
            ) : (
              <ul className="grid menu-grid">
                {menuItems.map((item) => (
                  <li key={item.id}>
                    <MenuItemCard item={item} onAdd={canAdd ? handleAdd : undefined} />
                  </li>
                ))}
              </ul>
            )}
            {(menuState.data.total > 0 || page > 1) && (
              <Pagination
                page={menuState.data.page}
                pageSize={menuState.data.page_size}
                total={menuState.data.total}
                onPageChange={(next) => setPageState({ key: filterKey, page: next })}
              />
            )}
          </>
        )}
      </section>

      <ReviewsSection restaurantId={id} />
    </main>
  );
}
