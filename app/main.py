from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import update
from starlette.middleware.sessions import SessionMiddleware
import bcrypt
import os
import secrets

from app.database import get_db, engine
from app.models import Base, User, Request as ServiceRequest, StatusEnum, RoleEnum

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Repair Service")
session_secret = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)
if len(session_secret) < 32:
    raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
app.add_middleware(
    SessionMiddleware, secret_key=session_secret, max_age=8 * 60 * 60,
    same_site="lax", https_only=os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true",
)
templates = Jinja2Templates(directory="app/templates")


def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if type(user_id) is not int or not 0 < user_id <= 2**63 - 1:
        return None
    return db.get(User, user_id)


def transition_request(db, req_id, allowed, target, *, owner_id=None, **values):
    if db.get(ServiceRequest, req_id) is None:
        raise HTTPException(status_code=404)
    statement = update(ServiceRequest).where(
        ServiceRequest.id == req_id, ServiceRequest.status.in_(allowed),
    )
    if owner_id is not None:
        statement = statement.where(ServiceRequest.assignedTo == owner_id)
    result = db.execute(statement.values(status=target, **values))
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=409, detail="Request unavailable or wrong status")


@app.get("/")
def create_request_form(request: Request):
    return templates.TemplateResponse("create_request.html", {"request": request})


@app.post("/")
def create_request(
    request: Request,
    clientName: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    problemText: str = Form(...),
    db: Session = Depends(get_db),
):
    new_req = ServiceRequest(
        clientName=clientName, phone=phone, address=address, problemText=problemText
    )
    db.add(new_req)
    db.commit()
    return templates.TemplateResponse(
        "create_request.html", {"request": request, "success": True}
    )


@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid credentials"}
        )
    resp = RedirectResponse(
        url="/dispatcher" if user.role == RoleEnum.dispatcher else "/master",
        status_code=302,
    )
    request.session.clear()
    request.session["user_id"] = user.id
    resp.delete_cookie("user_id")
    return resp


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("user_id")
    return resp


@app.get("/dispatcher")
def dispatcher_panel(
    request: Request,
    status: str = None,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.dispatcher:
        return RedirectResponse(url="/login", status_code=302)
    query = db.query(ServiceRequest)
    if status:
        query = query.filter(ServiceRequest.status == status)
    requests = query.order_by(ServiceRequest.createdAt.desc()).all()
    masters = db.query(User).filter(User.role == RoleEnum.master).all()
    return templates.TemplateResponse(
        "dispatcher.html",
        {"request": request, "requests": requests, "masters": masters,
         "current_status": status, "statuses": [s.value for s in StatusEnum]},
    )


@app.post("/dispatcher/assign/{req_id}")
def assign_master(
    req_id: int,
    request: Request,
    master_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.dispatcher:
        raise HTTPException(status_code=403)
    master = db.get(User, master_id)
    if not master or master.role != RoleEnum.master:
        raise HTTPException(status_code=400, detail="Select an existing master")
    transition_request(db, req_id, [StatusEnum.new, StatusEnum.assigned],
                       StatusEnum.assigned, assignedTo=master.id)
    return RedirectResponse(url="/dispatcher", status_code=302)


@app.post("/dispatcher/cancel/{req_id}")
def cancel_request(
    req_id: int, request: Request, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.dispatcher:
        raise HTTPException(status_code=403)
    transition_request(db, req_id, [StatusEnum.new, StatusEnum.assigned, StatusEnum.in_progress],
                       StatusEnum.canceled)
    return RedirectResponse(url="/dispatcher", status_code=302)


@app.get("/master")
def master_panel(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.master:
        return RedirectResponse(url="/login", status_code=302)
    requests = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.assignedTo == user.id)
        .order_by(ServiceRequest.createdAt.desc())
        .all()
    )
    return templates.TemplateResponse(
        "master.html", {"request": request, "requests": requests, "user": user}
    )


@app.post("/master/take/{req_id}")
def take_request(req_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.master:
        raise HTTPException(status_code=403)
    transition_request(db, req_id, [StatusEnum.assigned], StatusEnum.in_progress,
                       owner_id=user.id)
    return RedirectResponse(url="/master", status_code=302)


@app.post("/master/done/{req_id}")
def done_request(req_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.master:
        raise HTTPException(status_code=403)
    transition_request(db, req_id, [StatusEnum.in_progress], StatusEnum.done,
                       owner_id=user.id)
    return RedirectResponse(url="/master", status_code=302)


@app.post("/api/requests/{req_id}/take")
def api_take_request(req_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.master:
        raise HTTPException(status_code=403)
    transition_request(db, req_id, [StatusEnum.assigned], StatusEnum.in_progress,
                       owner_id=user.id)
    return {"status": "ok"}
