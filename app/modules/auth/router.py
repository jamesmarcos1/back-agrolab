from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.schemas import (
    ChallengeOutput,
    DeleteInput,
    EmailInput,
    LoginInput,
    RefreshInput,
    RegisterInput,
    ResendInput,
    ResetInput,
    SessionOutput,
    UserOutput,
    VerifyInput,
)
from app.modules.auth.service import perform, user_output

router = APIRouter(prefix="/api/v1", tags=["Autenticação"])
DB = Annotated[Session, Depends(get_db)]
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/auth/register", status_code=202, response_model=ChallengeOutput)
def register(data: RegisterInput, request: Request, db: DB):
    return perform(db, request, lambda service: service.register(data))


@router.post("/auth/verify-email", status_code=201, response_model=SessionOutput)
def verify(data: VerifyInput, request: Request, db: DB):
    return perform(db, request, lambda service: service.verify(data))


@router.post("/auth/resend-code", status_code=202, response_model=ChallengeOutput)
def resend(data: ResendInput, request: Request, db: DB):
    return perform(db, request, lambda service: service.resend(data))


@router.post("/auth/login", response_model=SessionOutput)
def login(data: LoginInput, request: Request, db: DB):
    return perform(db, request, lambda service: service.login(data))


@router.post("/auth/refresh", response_model=SessionOutput)
def refresh(data: RefreshInput, request: Request, db: DB):
    return perform(db, request, lambda service: service.refresh(data))


@router.post("/auth/logout", status_code=204)
def logout(data: RefreshInput, request: Request, db: DB):
    perform(db, request, lambda service: service.logout(data))
    return Response(status_code=204)


@router.get("/users/me", response_model=UserOutput, dependencies=[Depends(bearer_scheme)])
def me(request: Request, db: DB):
    return perform(db, request, lambda service: user_output(service.authenticate()))


@router.post("/auth/forgot-password", status_code=202)
def forgot(data: EmailInput, request: Request, db: DB):
    return perform(db, request, lambda service: service.forgot(data))


@router.post("/auth/reset-password", status_code=204)
def reset(data: ResetInput, request: Request, db: DB):
    perform(db, request, lambda service: service.reset(data))
    return Response(status_code=204)


@router.delete("/users/me", status_code=202, dependencies=[Depends(bearer_scheme)])
def delete_account(data: DeleteInput, request: Request, db: DB):
    return perform(db, request, lambda service: service.delete_account(data))
