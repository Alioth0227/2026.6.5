from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
import json

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========== Dify 配置 ==========
DIFY_KEY = "app-rWVZbMbkMsYlwd2WurImwwEe"
DIFY_URL = "https://api.dify.ai/v1/chat-messages"

# ========== 数据存储 ==========
# 存储每个用户的会话信息：job, resume, mode, history, conversation_id
sessions = {}

# ========== mode 映射表 ==========
MODE_MAP = {
    "练习模式": "practice",
    "标准面试": "normal",
    "压力面试": "stress",
    "practice": "practice",
    "normal": "normal",
    "stress": "stress"
}


# ========== 请求模型 ==========
class StartRequest(BaseModel):
    job: str
    resume: str
    mode: str
    user: str = "user-001"


class ChatRequest(BaseModel):
    message: str
    user: str = "user-001"


class ReportRequest(BaseModel):
    user: str = "user-001"


# ========== 路由 ==========
@app.get("/", response_class=HTMLResponse)
def home():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


@app.post("/api/start")
async def start_interview(request: StartRequest):
    user = request.user
    dify_mode = MODE_MAP.get(request.mode, "practice")

    # 初始化用户会话（字典结构）
    sessions[user] = {
        "job": request.job,
        "resume": request.resume,
        "mode": dify_mode,
        "history": [],
        "conversation_id": ""
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                DIFY_URL,
                headers={
                    "Authorization": f"Bearer {DIFY_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "query": "开始面试",
                    "inputs": {
                        "job_position": request.job,
                        "resume": request.resume,
                        "mode": dify_mode,
                        "force_report": False
                    },
                    "response_mode": "blocking",
                    "user": user
                }
            )

            data = response.json()
            print(f"Dify返回: {json.dumps(data, ensure_ascii=False)}")

            if "code" in data and data.get("status") == 400:
                return {"error": data.get("message", "Dify参数错误")}

            answer = data.get("answer", "无回复")
            sessions[user]["conversation_id"] = data.get("conversation_id", "")
            sessions[user]["history"].append({"role": "ai", "content": answer})

            return {"answer": answer, "conversation_id": sessions[user]["conversation_id"]}

        except Exception as e:
            print(f"请求异常: {e}")
            return {"error": f"请求异常: {str(e)}"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    user = request.user
    if user not in sessions:
        return {"error": "请先调用 /api/start 开始面试"}

    session = sessions[user]

    # 保存用户消息
    session["history"].append({"role": "user", "content": request.message})

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                DIFY_URL,
                headers={
                    "Authorization": f"Bearer {DIFY_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "query": request.message,
                    "inputs": {
                        "job_position": session["job"],
                        "resume": session["resume"],
                        "mode": session["mode"],
                        "force_report": False
                    },
                    "conversation_id": session["conversation_id"] or None,
                    "response_mode": "blocking",
                    "user": user
                }
            )

            data = response.json()
            print(f"Chat Dify返回: {json.dumps(data, ensure_ascii=False)}")

            if "code" in data and data.get("status") == 400:
                return {"error": data.get("message", "Dify参数错误")}

            answer = data.get("answer", "无回复")
            session["conversation_id"] = data.get("conversation_id", session["conversation_id"])
            session["history"].append({"role": "ai", "content": answer})

            return {"answer": answer, "conversation_id": session["conversation_id"]}

        except Exception as e:
            print(f"Chat请求异常: {e}")
            return {"error": f"请求异常: {str(e)}"}


@app.post("/api/report")
async def generate_report(request: ReportRequest):
    user = request.user
    if user not in sessions:
        return {"error": "没有找到面试记录"}

    session = sessions[user]

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                DIFY_URL,
                headers={
                    "Authorization": f"Bearer {DIFY_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "query": "请生成面试评估报告",
                    "inputs": {
                        "job_position": session["job"],
                        "resume": session["resume"],
                        "mode": session["mode"],
                        "force_report": True
                    },
                    "conversation_id": session["conversation_id"] or None,
                    "response_mode": "blocking",
                    "user": user
                }
            )

            data = response.json()
            print(f"Report Dify返回: {json.dumps(data, ensure_ascii=False)}")

            if "code" in data and data.get("status") == 400:
                return {"error": data.get("message", "Dify参数错误")}

            report = data.get("answer", "生成失败")
            return {"report": report}

        except Exception as e:
            print(f"Report请求异常: {e}")
            return {"error": f"请求异常: {str(e)}"}


@app.get("/api/health")
def health():
    return {"status": "ok"}