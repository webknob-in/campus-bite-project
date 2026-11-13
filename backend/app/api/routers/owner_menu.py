"""Restaurant owner menu management (Req 16, 40.2).

Every route requires the RESTAURANT_OWNER role and works on the owner's own restaurant only; a
Menu_Item of another restaurant (or a non-existent id) is a 404.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_owner_restaurant
from app.core.errors import NotFoundError
from app.models import MenuItem, Restaurant
from app.schemas.common import Page, PageParams
from app.schemas.menu import MenuItemOut
from app.schemas.owner_menu import AvailabilityIn, MenuItemCreate, MenuItemUpdate
from app.services.ids import fits_int32
from app.services.pagination import paginate
from app.services.text_search import clean_search, contains_ci

router = APIRouter(prefix="/owner/menu-items", tags=["owner-menu"])

_RESPONSES = {
    401: {"description": "Missing or invalid token."},
    403: {"description": "Not a RESTAURANT_OWNER."},
}
_ITEM_RESPONSES = {
    **_RESPONSES,
    404: {"description": "Menu item not found in the owner's restaurant."},
    422: {"description": "Invalid request body."},
}


def _get_own_item(db: Session, restaurant: Restaurant, item_id: int) -> MenuItem:
    # Ids beyond the INTEGER column range cannot exist; answer 404 instead of a database error.
    item = None
    if fits_int32(item_id):
        item = db.scalar(
            select(MenuItem).where(MenuItem.id == item_id, MenuItem.restaurant_id == restaurant.id)
        )
    if item is None:
        raise NotFoundError("Menu item not found")
    return item


@router.get(
    "",
    response_model=Page[MenuItemOut],
    summary="List the owner's menu items",
    responses=_RESPONSES,
)
def list_menu_items(
    search: Annotated[
        str | None, Query(description="Case-insensitive substring match on the name (literal text).")
    ] = None,
    params: PageParams = Depends(),
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> Page[MenuItemOut]:
    stmt = select(MenuItem).where(MenuItem.restaurant_id == restaurant.id)
    term = clean_search(search)
    if term is not None:
        stmt = stmt.where(contains_ci(MenuItem.name, term))
    page = paginate(db, stmt.order_by(MenuItem.name, MenuItem.id), params)
    return Page[MenuItemOut](**page)


@router.post(
    "",
    response_model=MenuItemOut,
    status_code=201,
    summary="Create a menu item",
    responses={**_RESPONSES, 422: {"description": "Invalid request body."}},
)
def create_menu_item(
    body: MenuItemCreate,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> MenuItem:
    item = MenuItem(restaurant_id=restaurant.id, **body.model_dump())
    db.add(item)
    db.flush()
    return item


@router.patch(
    "/{item_id}",
    response_model=MenuItemOut,
    summary="Update the supplied fields of a menu item",
    responses=_ITEM_RESPONSES,
)
def update_menu_item(
    item_id: int,
    body: MenuItemUpdate,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> MenuItem:
    item = _get_own_item(db, restaurant, item_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.flush()
    return item


@router.patch(
    "/{item_id}/availability",
    response_model=MenuItemOut,
    summary="Mark a menu item available or unavailable",
    responses=_ITEM_RESPONSES,
)
def set_availability(
    item_id: int,
    body: AvailabilityIn,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> MenuItem:
    item = _get_own_item(db, restaurant, item_id)
    item.is_available = body.is_available
    db.flush()
    return item


@router.delete(
    "/{item_id}",
    status_code=204,
    response_class=Response,
    summary="Delete a menu item",
    responses={**_RESPONSES, 404: _ITEM_RESPONSES[404]},
)
def delete_menu_item(
    item_id: int,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> Response:
    """Order_Item snapshots survive: ``order_items.menu_item_id`` is ``ON DELETE SET NULL``."""
    item = _get_own_item(db, restaurant, item_id)
    db.delete(item)
    db.flush()
    return Response(status_code=204)
