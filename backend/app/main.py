from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.venues import router as venues_router
from app.api.tables import router as tables_router
from app.api.categories import router as categories_router
from app.api.dishes import router as dishes_router
from app.api.menu import router as menu_router
from app.api.parse import router as parse_router
from app.api.qr import router as qr_router

app = FastAPI(title="MenuScan API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(venues_router)
app.include_router(tables_router)
app.include_router(categories_router)
app.include_router(dishes_router)
app.include_router(menu_router)
app.include_router(parse_router)
app.include_router(qr_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
