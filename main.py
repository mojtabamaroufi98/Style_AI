from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agent import run_agent
from models import ChatRequest, ChatResponse


app = FastAPI(
    title="StyleAI API",
    description="Backend API for StyleAI Personal Stylist",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "app": "StyleAI",
        "message": "StyleAI backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    try:
        answer, products = run_agent(
            message=request.message,
            profile=request.profile
        )

        return ChatResponse(
            answer=answer,
            products=products
        )

    except Exception as e:
        print("STYLEAI ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )