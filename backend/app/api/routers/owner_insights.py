"""Restaurant owner statistics and reminders (Req 19, 31, 40.10)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_owner_restaurant
from app.models import Restaurant
from app.models.admin_reminder_log import AdminReminderLog
from app.schemas.common import Page, PageParams
from app.schemas.reminder import ReminderOut
from app.schemas.stats import StatsOut
from app.services import reminder_service, stats_service
from app.services.pagination import paginate

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
    background_tasks: BackgroundTasks,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> StatsOut:
    # Looked up at call time so tests can patch it; runs after the response is sent.
    background_tasks.add_task(reminder_service.run_reminders_job)
    return stats_service.restaurant_stats(db, restaurant.id)


@router.get(
    "/reminders",
    response_model=Page[ReminderOut],
    summary="List my restaurant's reminders",
    responses={**_RESPONSES, 422: {"description": "Invalid filter or paging parameter."}},
)
def list_reminders(
    background_tasks: BackgroundTasks,
    resolved: bool | None = Query(default=None, description="Filter by resolved state"),
    params: PageParams = Depends(),
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> Page[ReminderOut]:
    background_tasks.add_task(reminder_service.run_reminders_job)
    stmt = select(AdminReminderLog).where(AdminReminderLog.restaurant_id == restaurant.id)
    if resolved is not None:
        stmt = stmt.where(AdminReminderLog.is_resolved.is_(resolved))
    stmt = stmt.order_by(AdminReminderLog.created_at.desc(), AdminReminderLog.id.desc())
    page = paginate(db, stmt, params)
    page["items"] = [ReminderOut.model_validate(r) for r in page["items"]]
    return Page[ReminderOut](**page)


@router.patch(
    "/reminders/{reminder_id}/resolve",
    response_model=ReminderOut,
    summary="Resolve a reminder",
    responses={**_RESPONSES, 404: {"description": "Reminder not found (or not in my restaurant)."}},
)
def resolve_reminder(
    reminder_id: int = Path(ge=1, le=2**63 - 1),
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> ReminderOut:
    reminder = db.scalars(
        select(AdminReminderLog).where(
            AdminReminderLog.id == reminder_id, AdminReminderLog.restaurant_id == restaurant.id
        )
    ).first()
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder.is_resolved = True
    db.flush()
    return ReminderOut.model_validate(reminder)
