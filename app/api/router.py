from fastapi import APIRouter

from app.api.v2 import setup, system
from app.api.v3 import auth as auth_v3
from app.api.v3 import ai as ai_v3
from app.api.v3 import admin_ai as admin_ai_v3
from app.api.v3 import chat_v3
from app.api.v3 import dashboard as dashboard_v3
from app.api.v3 import meals as meals_v3
from app.api.v3 import nutrition as nutrition_v3
from app.api.v3 import plans as plans_v3
from app.api.v3 import rbac
from app.api.v3 import training as training_v3
from app.api.v3 import workouts as workouts_v3
from app.modules.users.router import router as users_router


api_router = APIRouter()

api_router.include_router(setup.router, prefix="/api/v2/setup", tags=["Setup Wizard"])
api_router.include_router(system.router, prefix="/api/v2/system", tags=["System Control"])
api_router.include_router(auth_v3.router, prefix="/api/v3/auth", tags=["Authentication V3"])
api_router.include_router(rbac.router, prefix="/api/v3/rbac", tags=["V3 Access Control"])
api_router.include_router(users_router, prefix="/api/v3/users", tags=["V3 User Management"])
api_router.include_router(ai_v3.router, prefix="/api/v3/ai", tags=["AI Feedback"])
api_router.include_router(admin_ai_v3.router, prefix="/api/v3/admin/ai", tags=["AI Control Plane"])
api_router.include_router(chat_v3.router, prefix="/api/v3/chat", tags=["Chat V3"])
api_router.include_router(nutrition_v3.router, prefix="/api/v3/nutrition", tags=["Nutrition Decision Support"])
api_router.include_router(training_v3.router, prefix="/api/v3/training", tags=["Training Decision Support"])
api_router.include_router(meals_v3.router, prefix="/api/v3/meals", tags=["Meal Logs"])
api_router.include_router(workouts_v3.router, prefix="/api/v3/workouts", tags=["Workout Logs"])
api_router.include_router(dashboard_v3.router, prefix="/api/v3/dashboard", tags=["Dashboard V3"])
api_router.include_router(plans_v3.router, prefix="/api/v3/plans", tags=["Plans V3"])
