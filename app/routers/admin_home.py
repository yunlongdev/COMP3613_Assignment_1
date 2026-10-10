from fastapi import Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AdminDep
from app.dependencies.session import SessionDep
from app.services.awards_service import VolunteerHourService
from app.utilities.flash import flash
from . import router, templates


@router.get("/admin", response_class=HTMLResponse, name="admin_home_view")
async def admin_home_view(
    request: Request,
    user: AdminDep,
    db: SessionDep,
):
    service = VolunteerHourService(db)
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            "pending_hours": service.get_pending(),
            "leaderboard": service.get_leaderboard(),
        },
    )


@router.post("/admin/approve-hour/{hour_id}", name="approve_hour")
async def approve_hour(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    hour_id: int,
):
    service = VolunteerHourService(db)
    try:
        service.approve(hour_id)
        flash(request, "Volunteer hours approved.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(url=request.url_for("admin_home_view"), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/reject-hour/{hour_id}", name="reject_hour")
async def reject_hour(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    hour_id: int,
):
    service = VolunteerHourService(db)
    try:
        service.reject(hour_id)
        flash(request, "Volunteer hours rejected.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(url=request.url_for("admin_home_view"), status_code=status.HTTP_303_SEE_OTHER)

