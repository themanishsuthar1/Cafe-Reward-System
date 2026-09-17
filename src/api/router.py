from fastapi import APIRouter
from src.api.routers.members import router as members_router
from src.api.routers.lookup import router as lookup_router
from src.api.routers.purchases import router as purchases_router
from src.api.routers.redemptions import router as redemptions_router
from src.api.routers.rewards import router as rewards_router
from src.api.routers.clock import router as clock_router
from src.api.routers.outbox import router as outbox_router

api_router = APIRouter(prefix="/api")

# Register sub-routers
api_router.include_router(members_router)
api_router.include_router(lookup_router)
api_router.include_router(purchases_router)
api_router.include_router(redemptions_router)
api_router.include_router(rewards_router)
api_router.include_router(clock_router)
api_router.include_router(outbox_router)
