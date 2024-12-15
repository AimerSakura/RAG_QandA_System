from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import os

from user_db import verify_user, register_user, init_db
from session_middleware import SessionMiddleware, create_session
from processor import process_rag

app = FastAPI()
app.add_middleware(SessionMiddleware)
init_db()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_current_user(request: Request):
    return request.state.user

def login_required(request: Request):
    return request.state.user is not None

def load_dependency_info():
    if os.path.exists("dependencies.json"):
        with open("dependencies.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    return None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login_action(request: Request, username: str = Form(...), password: str = Form(...)):
    if verify_user(username, password):
        response = templates.TemplateResponse("index.html", {"request": request, "user": username})
        create_session(response, username)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "用户名或密码错误"})

@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    response = HTMLResponse("注销成功！<a href='/'>返回首页</a>")
    response.delete_cookie("session_id")
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register_action(request: Request, username: str = Form(...), password: str = Form(...), password_confirm: str = Form(...)):
    if password != password_confirm:
        return templates.TemplateResponse("register.html", {"request": request, "error": "两次输入的密码不一致"})

    success, msg = register_user(username, password)
    if success:
        response = templates.TemplateResponse("index.html", {"request": request, "user": username})
        create_session(response, username)
        return response
    else:
        return templates.TemplateResponse("register.html", {"request": request, "error": msg})

@app.post("/ask", response_class=HTMLResponse)
async def ask_question(request: Request,
                       question: str = Form(...),
                       file: UploadFile = File(None)):
    if not login_required(request):
        return HTMLResponse("<h1>请先登录</h1><a href='/login'>登录</a>", status_code=403)

    user = get_current_user(request)
    content_str = ""
    if file is not None:
        content = await file.read()
        content_str = content.decode('utf-8')

    result = process_rag(content_str, question, user=user)
    return templates.TemplateResponse("result.html", {"request": request, "result": result, "user": user})

@app.get("/admin/dependencies", response_class=HTMLResponse)
async def admin_dependencies(request: Request):
    if not login_required(request):
        return HTMLResponse("<h1>请先登录</h1><a href='/login'>登录</a>", status_code=403)

    data = load_dependency_info()
    if data:
        return templates.TemplateResponse("admin.html", {"request": request, "data": data})
    else:
        return HTMLResponse("No dependency analysis data found.", status_code=404)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
