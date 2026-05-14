from fastapi import APIRouter

from backend.main import ChatRequest, chat

router = APIRouter()


@router.post("/chat")
async def chat_route(request: ChatRequest):
    return await chat(request)
