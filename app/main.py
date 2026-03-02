from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import update
import bcrypt

from app.database import get_db, engine
from app.models import Base, User, Request as ServiceRequest, StatusEnum, RoleEnum

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Repair Service")
templates = Jinja2Templates(directory="app/templates")


def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id)).first()


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
    resp.set_cookie("user_id", str(user.id))
    return resp


@app.get("/logout")
def logout():
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
    req = db.query(ServiceRequest).filter(ServiceRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404)
    req.assignedTo = master_id
    req.status = StatusEnum.assigned
    db.commit()
    return RedirectResponse(url="/dispatcher", status_code=302)


@app.post("/dispatcher/cancel/{req_id}")
def cancel_request(
    req_id: int, request: Request, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.dispatcher:
        raise HTTPException(status_code=403)
    req = db.query(ServiceRequest).filter(ServiceRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404)
    req.status = StatusEnum.canceled
    db.commit()
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
    result = db.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == req_id,
            ServiceRequest.status == StatusEnum.assigned,
        )
        .values(status=StatusEnum.in_progress)
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=409, detail="Request already taken or wrong status")
    return RedirectResponse(url="/master", status_code=302)


@app.post("/master/done/{req_id}")
def done_request(req_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != RoleEnum.master:
        raise HTTPException(status_code=403)
    req = db.query(ServiceRequest).filter(ServiceRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404)
    req.status = StatusEnum.done
    db.commit()
    return RedirectResponse(url="/master", status_code=302)


@app.post("/api/requests/{req_id}/take")
def api_take_request(req_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        update(ServiceRequest)
        .where(
            ServiceRequest.id == req_id,
            ServiceRequest.status == StatusEnum.assigned,
        )
        .values(status=StatusEnum.in_progress)
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=409, detail="Conflict: already taken")
    return {"status": "ok"}
