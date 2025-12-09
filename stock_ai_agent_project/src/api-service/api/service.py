from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import os

# from api.routers import newsletter, podcast

# from api.routers import llm_chat, llm_cnn_chat
# from api.routers import llm_rag_chat, llm_agent_chat
from api.routers import chatbot_final, stock_details

# from api.routers import test_router

# Setup FastAPI app
# app = FastAPI(title="API Server", description="API Server", version="v1")
app = FastAPI(
    title="API Server",
    description="API Server",
    version="v1",
    root_path=os.getenv("ROOT_PATH", ""),
)

# Enable CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routes
@app.get("/")
async def get_index():
    return {"message": "Welcome to Stockbusters"}


@app.get("/square_root/")
async def square_root(x: float = 1, y: float = 2):
    z = x**2 + y**2
    return z**0.5


app.include_router(chatbot_final.router)
app.include_router(stock_details.router)
