from datetime import date

from fastapi import Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AuthDep, get_optional_current_user
from app.dependencies.session import SessionDep
from app.models.user import User
from app.repositories.awards import AwardRepository
from app.services.awards_service import AwardService, VolunteerHourService
from app.utilities.flash import flash
from . import router, templates


@router.get("/app/log-hours", response_class=HTMLResponse, name="log_hours_view")
@router.get("/app", response_class=HTMLResponse, name="user_home_view")
async def log_hours_view(
    request: Request,
    user: AuthDep,
):
    return templates.TemplateResponse(
        request=request,
        name="log-hours.html",
        context={
            "user": user,
        },
    )


@router.get("/leaderboard", response_class=HTMLResponse, name="leaderboard_view")
async def leaderboard_view(
    request: Request,
    db: SessionDep,
    user: User | None = Depends(get_optional_current_user),
):
    service = VolunteerHourService(db)
    return templates.TemplateResponse(
        request=request,
        name="leaderboard.html",
        context={"leaderboard": service.get_leaderboard(), "user": user},
    )


@router.get("/app/prizes", response_class=HTMLResponse, name="prizes_view")
async def prizes_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    hour_service = VolunteerHourService(db)
    award_service = AwardService(db)
    return templates.TemplateResponse(
        request=request,
        name="prizes.html",
        context={
            "user": user,
            "awards": award_service.list_awards(),
            "balance": hour_service.get_balance(user.id),
        },
    )


@router.post("/app/volunteer-hours", name="submit_volunteer_hours")
async def submit_volunteer_hours(
    request: Request,
    db: SessionDep,
    user: AuthDep,
    activity_name: str = Form(...),
    volunteer_date: date = Form(...),
    description: str = Form(""),
    hours: float = Form(...),
):
    try:
        service = VolunteerHourService(db)
        service.submit_hours(
            student_id=user.id,
            activity_name=activity_name,
            volunteer_date=volunteer_date,
            description=description,
            hours=hours,
        )
        flash(request, "Volunteer hours submitted for approval.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    except Exception:
        flash(request, "Could not submit volunteer hours.", "danger")
    return RedirectResponse(url=request.url_for("log_hours_view"), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/app/redeem-award/{award_id}", name="redeem_award")
async def redeem_award(
    request: Request,
    db: SessionDep,
    user: AuthDep,
    award_id: int,
):
    service = VolunteerHourService(db)
    award_repo = AwardRepository(db)
    try:
        award = award_repo.get_by_id(award_id)
        if award is None:
            raise ValueError("Award not found")
        balance = service.get_balance(user.id)
        award_service = AwardService(db)
        award_service.redeem(user.id, award_id, balance)
        flash(request, f"You redeemed {award.name}.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(url=request.url_for("prizes_view"), status_code=status.HTTP_303_SEE_OTHER)
