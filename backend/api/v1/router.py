from fastapi import APIRouter

from api.v1.routes.analyze        import router as analyze_router
from api.v1.routes.recompute      import router as recompute_router
from api.v1.routes.jobs           import router as jobs_router
from api.v1.routes.methods        import router as methods_router
from api.v1.routes.export         import router as export_router
from api.v1.routes.history        import router as history_router
from api.v1.routes.settings_route import router as settings_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(analyze_router,   tags=["Analysis"])
api_router.include_router(recompute_router, tags=["Analysis"])
api_router.include_router(jobs_router,      tags=["Jobs"])
api_router.include_router(methods_router,   tags=["Methods"])
api_router.include_router(export_router,    tags=["Export"])
api_router.include_router(history_router,   tags=["History"])
api_router.include_router(settings_router,  tags=["Settings"])