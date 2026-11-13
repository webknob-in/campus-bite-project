// NotFound: catch-all page for unknown URLs (Requirement 32.3).
import { Link } from "react-router-dom";
import "../styles/pages/NotFound.css";

export default function NotFound() {
  return (
    <section className="not-found" aria-labelledby="not-found-title">
      <p className="not-found-code" aria-hidden="true">
        404
      </p>
      <h1 id="not-found-title" className="page-title">
        Page not found
      </h1>
      <p className="not-found-text">The page you are looking for does not exist or has moved.</p>
      <Link to="/" className="btn btn-primary">
        Go to home
      </Link>
    </section>
  );
}
