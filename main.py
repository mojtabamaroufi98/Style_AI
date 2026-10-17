from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agent import run_agent
from memory import memory
from models import ChatRequest, ChatResponse


app = FastAPI(
    title="StyleAI API",
    description="Backend API for StyleAI Personal Stylist",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "app": "StyleAI",
        "message": "StyleAI backend is running"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# =========================================================
# CHAT
# =========================================================

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    try:

        # اگر session_id ارسال نشده باشد،
        # یک session پیش‌فرض استفاده می‌شود.
        session_id = request.session_id or "default"

        # -------------------------------------------------
        # Save user message
        # -------------------------------------------------

        memory.add_message(
            session_id=session_id,
            role="user",
            content=request.message
        )

        # -------------------------------------------------
        # Get conversation history
        # -------------------------------------------------

        conversation = memory.get_messages(
            session_id
        )

        # پیام فعلی را از history جدا می‌کنیم
        # چون قرار است جداگانه به Agent داده شود.
        history = conversation[:-1]

        # -------------------------------------------------
        # Run Agent
        # -------------------------------------------------

        answer, products = run_agent(
            message=request.message,
            profile=request.profile,
            conversation=history
        )

        # -------------------------------------------------
        # Save AI response
        # -------------------------------------------------

        memory.add_message(
            session_id=session_id,
            role="assistant",
            content=answer
        )

        # -------------------------------------------------
        # Response
        # -------------------------------------------------

        return ChatResponse(
            answer=answer,
            products=products
        )

    except Exception as e:

        print(
            "STYLEAI ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )