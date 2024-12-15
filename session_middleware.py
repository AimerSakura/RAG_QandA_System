# session_middleware.py
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

SESSION_COOKIE_NAME = "session_id"
sessions = {}

class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if session_id and session_id in sessions:
            request.state.user = sessions[session_id].get("username")
        else:
            request.state.user = None
        response = await call_next(request)
        return response

def create_session(response: Response, username: str):
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"username": username}
    response.set_cookie(key=SESSION_COOKIE_NAME, value=session_id, httponly=True)

def logout_session(response: Response):
    session_id = response.cookies.get(SESSION_COOKIE_NAME)
    if session_id in sessions:
        del sessions[session_id]
    response.delete_cookie(SESSION_COOKIE_NAME)
