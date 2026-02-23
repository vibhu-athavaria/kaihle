
from fastapi import APIRouter
from app.api.v1 import auth, badge, users, students, progress, assessments, study_plans, ai_tutor, course, notifications, billing, grades, diagnostic

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(students.router, prefix="/students", tags=["students"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(course.router, prefix="/course", tags=["courses"])
api_router.include_router(study_plans.router, prefix="/study-plans", tags=["study-plans"])
api_router.include_router(ai_tutor.router, prefix="/ai-tutor", tags=["ai-tutor"])
api_router.include_router(grades.router, prefix="/grades", tags=["grades"])
# api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(badge.router, prefix="/badges", tags=["badges"])
api_router.include_router(diagnostic.router, prefix="/diagnostic", tags=["diagnostic"])