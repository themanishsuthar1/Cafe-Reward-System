import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.storage.database import init_db, seed_default_rewards, get_connection, DEFAULT_DB_PATH
from src.services.lookup_service import MemberLookupService
from src.api import api_router
from src.auth.router import router as auth_router
from src.logger import get_logger

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Café Counter Loyalty System API Application...")
    # Initialize DB schema (includes users table + EXPIRATION migration) & seed rewards
    init_db(DEFAULT_DB_PATH)
    seed_default_rewards(DEFAULT_DB_PATH)

    # Seed sample members if empty for counter demo convenience
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        lookup_svc = MemberLookupService(DEFAULT_DB_PATH)
        existing = lookup_svc.search_members(conn, "")
        if not existing:
            m1 = lookup_svc.register_member(conn, "Jane Doe (Base)", "555-100-2000")
            m2 = lookup_svc.register_member(conn, "Marcus Aurelius (Silver)", "555-200-3000")
            m3 = lookup_svc.register_member(conn, "Sophia Chen (Gold)", "555-300-4000")

            # Seed initial purchases to populate tiers
            from src.services.purchase_service import PurchaseService
            p_svc = PurchaseService(DEFAULT_DB_PATH)
            p_svc.record_purchase(conn, m2["id"], 600.0, "seed_m2_purchase", terminal_id="TERM_1")
            p_svc.record_purchase(conn, m3["id"], 1200.0, "seed_m3_purchase_1", terminal_id="TERM_1")
            # 1200 * 1.25 = 1500 → triggers GOLD tier
            p_svc.record_purchase(conn, m3["id"], 300.0, "seed_m3_purchase_2", terminal_id="TERM_1")
    finally:
        conn.close()

    yield


app = FastAPI(
    title="Café Counter Points-and-Tiers Loyalty API",
    description=(
        "Financial-grade loyalty points & tier management built on an append-only ledger. "
        "Use **POST /auth/register** to create a staff account, then **POST /auth/login** "
        "to obtain a Bearer token and authorize all write endpoints."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend served from same origin + any local dev ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Auth Router (open: register, login)
app.include_router(auth_router)

# Mount Modular API Router (write endpoints protected via get_current_user)
app.include_router(api_router)

# Mount Static UI directory
UI_DIR = os.path.join(os.path.dirname(__file__), "ui")
if os.path.exists(UI_DIR):
    app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.get("/", include_in_schema=False)
def serve_index():
    index_path = os.path.join(UI_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "Café Loyalty API is running."})


@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "system": "Cafe Rewards Ledger"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
