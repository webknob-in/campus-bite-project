"""APScheduler wiring for the reminder job (Req 31.5). Started only when ENABLE_SCHEDULER=true."""

from apscheduler.schedulers.background import BackgroundScheduler

from app.services.reminder_service import run_reminders_job

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_reminders_job,
        "interval",
        seconds=60,
        id="reminders",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
