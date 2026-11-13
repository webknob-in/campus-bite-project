"""Restaurant owner statistics (Req 19, 40.10). Reminder endpoints are added by task 10.2."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_owner_restaurant
from app.models import Restaurant
from app.schemas.stats import StatsOut
from app.services import stats_service

router = APIRouter(prefix="/owner", tags=["owner-insights"])

_RESPONSES = {
    401: {"description": "Missing or invalid token."},
    403: {"description": "Not a RESTAURANT_OWNER."},
}


@router.get(
    "/stats",
    response_model=StatsOut,
    summary="Statistics for my restaurant",
    responses={**_RESPONSES, 404: {"description": "The owner has no restaurant."}},
)
def get_stats(
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> StatsOut:
    return stats_service.restaurant_stats(db, restaurant.id)
