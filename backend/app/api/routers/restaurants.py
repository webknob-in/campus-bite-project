"""Public browsing: restaurants, menus, dish search and reviews (Req 8, 9, 40.2). No auth."""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import NotFoundError
from app.models import MenuItem, Restaurant, Review, User
from app.schemas.common import Page, PageParams
from app.schemas.menu import DishOut, MenuItemOut, ReviewOut
from app.schemas.restaurant import RestaurantOut
from app.services.pagination import paginate
from app.services.text_search import clean_search, contains_ci

router = APIRouter(tags=["restaurants"])

MAX_INT = 2**31 - 1  # PostgreSQL INTEGER

SearchQuery = Annotated[
    str | None,
    Query(description="Case-insensitive substring match (literal text, no wildcards)."),
]


class DishFilters:
    """``search``, ``min_price`` and ``max_price`` query parameters shared by the dish endpoints.

    Prices must be numbers >= 0 (FastAPI returns 422 otherwise) and ``min_price`` must not
    exceed ``max_price`` (Req 9.5).
    """

    def __init__(
        self,
        search: SearchQuery = None,
        min_price: Annotated[
            Decimal | None, Query(ge=0, description="Minimum price (inclusive).")
        ] = None,
        max_price: Annotated[
            Decimal | None, Query(ge=0, description="Maximum price (inclusive).")
        ] = None,
    ) -> None:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("query", "min_price"),
                        "msg": "min_price must be less than or equal to max_price",
                        "input": str(min_price),
                    }
                ]
            )
        self.search = clean_search(search)
        self.min_price = min_price
        self.max_price = max_price

    def apply(self, stmt: Select) -> Select:
        if self.search is not None:
            stmt = stmt.where(contains_ci(MenuItem.name, self.search))
        if self.min_price is not None:
            stmt = stmt.where(MenuItem.price >= self.min_price)
        if self.max_price is not None:
            stmt = stmt.where(MenuItem.price <= self.max_price)
        return stmt


def _get_restaurant_or_404(db: Session, restaurant_id: int) -> Restaurant:
    # Ids beyond the INTEGER column range cannot exist; answer 404 instead of a database error.
    restaurant = db.get(Restaurant, restaurant_id) if -MAX_INT <= restaurant_id <= MAX_INT else None
    if restaurant is None:
        raise NotFoundError("Restaurant not found")
    return restaurant


def _restaurant_outs(db: Session, restaurants: list[Restaurant]) -> list[RestaurantOut]:
    """Build ``RestaurantOut`` rows with ratings from a single aggregate query (no N+1)."""
    stats: dict[int, tuple[float | None, int]] = {}
    if restaurants:
        rows = db.execute(
            select(Review.restaurant_id, func.avg(Review.rating), func.count(Review.id))
            .where(Review.restaurant_id.in_([r.id for r in restaurants]))
            .group_by(Review.restaurant_id)
        ).all()
        stats = {rid: (round(float(avg), 2), int(count)) for rid, avg, count in rows}
    outs = []
    for restaurant in restaurants:
        average, count = stats.get(restaurant.id, (None, 0))
        out = RestaurantOut.model_validate(restaurant)
        out.average_rating = average
        out.review_count = count
        outs.append(out)
    return outs


@router.get("/restaurants", response_model=Page[RestaurantOut], summary="List restaurants")
def list_restaurants(
    search: SearchQuery = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> Page[RestaurantOut]:
    """Restaurants ordered by name, with average rating. ``search`` matches name or cuisine."""
    stmt = select(Restaurant)
    term = clean_search(search)
    if term is not None:
        stmt = stmt.where(contains_ci(Restaurant.name, term) | contains_ci(Restaurant.cuisine, term))
    page = paginate(db, stmt.order_by(Restaurant.name, Restaurant.id), params)
    page["items"] = _restaurant_outs(db, page["items"])
    return Page[RestaurantOut](**page)


@router.get(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantOut,
    summary="Restaurant details",
    responses={404: {"description": "Restaurant not found."}},
)
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db)) -> RestaurantOut:
    restaurant = _get_restaurant_or_404(db, restaurant_id)
    return _restaurant_outs(db, [restaurant])[0]


@router.get(
    "/restaurants/{restaurant_id}/menu",
    response_model=Page[MenuItemOut],
    summary="A restaurant's menu",
    responses={404: {"description": "Restaurant not found."}, 422: {"description": "Invalid filters."}},
)
def get_menu(
    restaurant_id: int,
    filters: DishFilters = Depends(),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> Page[MenuItemOut]:
    """All of the restaurant's dishes (unavailable ones included, flagged ``is_available``)."""
    _get_restaurant_or_404(db, restaurant_id)
    stmt = filters.apply(select(MenuItem).where(MenuItem.restaurant_id == restaurant_id))
    page = paginate(db, stmt.order_by(MenuItem.name, MenuItem.id), params)
    return Page[MenuItemOut](**page)


@router.get(
    "/dishes",
    response_model=Page[DishOut],
    summary="Search dishes across all restaurants",
    responses={422: {"description": "Invalid filters."}},
)
def search_dishes(
    filters: DishFilters = Depends(),
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> Page[DishOut]:
    stmt = filters.apply(
        select(MenuItem, Restaurant.name.label("restaurant_name")).join(
            Restaurant, Restaurant.id == MenuItem.restaurant_id
        )
    )
    page = paginate(db, stmt.order_by(MenuItem.name, MenuItem.id), params)
    page["items"] = [
        DishOut(
            **MenuItemOut.model_validate(item).model_dump(),
            restaurant_name=restaurant_name,
        )
        for item, restaurant_name in page["items"]
    ]
    return Page[DishOut](**page)


@router.get(
    "/restaurants/{restaurant_id}/reviews",
    response_model=Page[ReviewOut],
    summary="A restaurant's reviews, newest first",
    responses={404: {"description": "Restaurant not found."}},
)
def get_reviews(
    restaurant_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
) -> Page[ReviewOut]:
    _get_restaurant_or_404(db, restaurant_id)
    stmt = (
        select(Review, User.name.label("customer_name"))
        .join(User, User.id == Review.customer_id)
        .where(Review.restaurant_id == restaurant_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
    )
    page = paginate(db, stmt, params)
    page["items"] = [
        ReviewOut(
            id=review.id,
            restaurant_id=review.restaurant_id,
            rating=review.rating,
            comment=review.comment,
            customer_name=customer_name,
            created_at=review.created_at,
        )
        for review, customer_name in page["items"]
    ]
    return Page[ReviewOut](**page)
