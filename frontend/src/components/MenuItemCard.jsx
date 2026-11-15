// MenuItemCard: a dish with name, description, price, category, image, and availability
// (Requirement 8.8). The add button is disabled and labelled "Unavailable" when the dish is not
// available. Pass `onAdd` to show the button (omit it for roles that cannot order) and
// `restaurantLink` to show a link to the dish's restaurant (dish search).
import { useState } from "react";
import { Link } from "react-router-dom";
import { formatPrice } from "../utils/money.js";
import "../styles/pages/BrowseCards.css";

export default function MenuItemCard({ item, onAdd, restaurantLink }) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = item.image_url && !imageFailed;

  return (
    <article className={`browse-card menu-item-card${item.is_available ? "" : " is-unavailable"}`}>
      <div className="browse-card-media">
        {showImage ? (
          <img src={item.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)} />
        ) : (
          <div className="browse-card-placeholder" aria-hidden="true">
            {item.name?.charAt(0)?.toUpperCase() || "?"}
          </div>
        )}
      </div>
      <div className="browse-card-body">
        <div className="browse-card-heading">
          <h3 className="browse-card-title">{item.name}</h3>
          <span className="menu-item-price">{formatPrice(item.price)}</span>
        </div>
        {item.category && <p className="browse-card-meta">{item.category}</p>}
        {item.description && <p className="browse-card-text">{item.description}</p>}
        {restaurantLink && (
          <p className="browse-card-meta">
            From{" "}
            <Link to={`/restaurants/${item.restaurant_id}`} className="restaurant-link">
              {item.restaurant_name}
            </Link>
          </p>
        )}
        <div className="menu-item-footer">
          <span className={`badge ${item.is_available ? "badge-success" : "badge-neutral"}`}>
            {item.is_available ? "Available" : "Not available"}
          </span>
          {onAdd && (
            <button
              type="button"
              className="btn btn-sm"
              disabled={!item.is_available}
              onClick={() => onAdd(item)}
              aria-label={item.is_available ? `Add ${item.name} to cart` : undefined}
            >
              {item.is_available ? "Add to cart" : "Unavailable"}
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
