// RestaurantCard: one restaurant in the list, linking to its menu page (Requirement 8.7).
import { useState } from "react";
import { Link } from "react-router-dom";
import RatingSummary from "./RatingSummary.jsx";
import "../styles/pages/BrowseCards.css";

export default function RestaurantCard({ restaurant }) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = restaurant.image_url && !imageFailed;

  return (
    <article className="browse-card restaurant-card">
      <Link to={`/restaurants/${restaurant.id}`} className="browse-card-link" aria-label={`View menu of ${restaurant.name}`}>
        <div className="browse-card-media">
          {showImage ? (
            <img src={restaurant.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)} />
          ) : (
            <div className="browse-card-placeholder" aria-hidden="true">
              {restaurant.name?.charAt(0)?.toUpperCase() || "?"}
            </div>
          )}
        </div>
        <div className="browse-card-body">
          <div className="browse-card-heading">
            <h3 className="browse-card-title">{restaurant.name}</h3>
            <span className={`badge ${restaurant.is_open ? "badge-success" : "badge-neutral"}`}>
              {restaurant.is_open ? "Open" : "Closed"}
            </span>
          </div>
          <p className="browse-card-meta">{restaurant.cuisine}</p>
          {restaurant.description && <p className="browse-card-text">{restaurant.description}</p>}
          <p className="browse-card-meta text-muted">{restaurant.address}</p>
          <RatingSummary average={restaurant.average_rating} count={restaurant.review_count} />
        </div>
      </Link>
    </article>
  );
}
