import sys
from pathlib import Path

# Ensure backend root is on Python sys.path for absolute imports
_BASE_DIR = Path(__file__).parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.exception_handler import register_exception_handlers
from app.voice.routes import router as voice_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.config.logging import setup_logging
from app.config.settings import settings 
from app.middleware.request_id import RequestIDMiddleware
from app.api.routes.auth import router as auth_router
from app.api.routes.user import router as user_router
from app.api.routes.booking import router as booking_router
from app.websocket.routes import router as websocket_router
from app.api.routes.trip import router as trip_router
setup_logging()
from fastapi.middleware.cors import CORSMiddleware
from app.core.lifespan import lifespan


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

origins = [
    "https://voice-based-customer-care-agent.vercel.app",
    "https://voice-based-customer-care-agent-1.onrender.com",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

raw_origins = getattr(settings, "allowed_origins", "") or ""
if raw_origins and raw_origins.strip() != "*":
    for o in raw_origins.split(","):
        if o.strip() and o.strip() not in origins:
            origins.append(o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path

# Use absolute paths so static files resolve correctly regardless of cwd
_BASE_DIR = Path(__file__).parent
_TEMP_DIR = _BASE_DIR / "temp"
_AUDIO_DIR = _BASE_DIR / "generated_audio"
_TEMP_DIR.mkdir(exist_ok=True)
_AUDIO_DIR.mkdir(exist_ok=True)

app.mount(
    "/generated_audio",
    StaticFiles(directory=str(_AUDIO_DIR)),
    name="generated_audio",
)
app.mount(
    "/temp",
    StaticFiles(directory=str(_TEMP_DIR)),
    name="temp",
)
app.include_router(voice_router)

app.include_router(
    trip_router,
    prefix="/api/v1/trips",
    tags=["Trips"],
)


from app.api.routes.conversation import router as conversation_router
from app.api.routes.complaint import router as complaint_router

app.include_router(booking_router)
app.include_router(user_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(complaint_router)
app.include_router(websocket_router)
register_exception_handlers(app)
app.include_router(health_router)
app.add_middleware(RequestIDMiddleware)
@app.get("/")
async def root():
    return {
        "message": "SupportAI Backend Running"
    }
print("\n========== ROUTES ==========")

for route in app.routes:
    methods = getattr(route, "methods", [])
    print(methods, route.path)

print("============================\n")