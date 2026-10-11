from fastapi import APIRouter, Depends, HTTPException, Request, Response

from outdoorwise.config import Settings

from .models import AccountCredentials, UserPublic, UsernameAvailability
from .repository import AccountRepository
from .security import clear_session_cookie, current_user_from_request, set_session_cookie
from .service import AccountService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_repository(): return AccountRepository(Settings.from_env().data_root)
def get_service(repo: AccountRepository = Depends(get_repository)): return AccountService(repo)
def get_current_user(request: Request, repo: AccountRepository = Depends(get_repository)): return current_user_from_request(request, repo)


@router.get("/username-availability", response_model=UsernameAvailability)
def username_availability(username: str, service: AccountService = Depends(get_service)):
    try: available = service.availability(username)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    return {"username": username, "available": available}


@router.post("/register", response_model=UserPublic, status_code=201)
def register(credentials: AccountCredentials, response: Response, service: AccountService = Depends(get_service)):
    try: user = service.register(credentials)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
    set_session_cookie(response, service.repository, user.user_id)
    return service.public(user)


@router.post("/login", response_model=UserPublic)
def login(credentials: AccountCredentials, response: Response, service: AccountService = Depends(get_service)):
    user = service.authenticate(credentials)
    if user is None: raise HTTPException(401, "Invalid username or password")
    set_session_cookie(response, service.repository, user.user_id)
    return service.public(user)


@router.get("/me", response_model=UserPublic)
def me(user: UserPublic = Depends(get_current_user)): return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, repo: AccountRepository = Depends(get_repository)):
    raw = request.cookies.get("outdoorwise_session")
    if raw:
        import hashlib
        repo.delete_session(hashlib.sha256(raw.encode()).hexdigest())
    clear_session_cookie(response)
