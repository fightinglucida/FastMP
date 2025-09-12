from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.me import router as me_router
from app.api.v1.routes.cookie import router as cookie_router
from app.api.v1.routes.activation import router as activation_router
from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.gzhaccount import router as gzhaccount_router
from app.api.v1.routes.gzharticle import router as gzharticle_router
from app.api.v1.routes.gzhaccount_admin_ops import router as gzhaccount_admin_ops_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(activation_router)
app.include_router(admin_router)
app.include_router(cookie_router)
app.include_router(gzhaccount_router)
app.include_router(gzharticle_router)
app.include_router(gzhaccount_admin_ops_router)


# Create tables on startup (for initial bootstrap; consider Alembic for production)
from app.db.base import Base  # noqa: E402
from app.db.session import engine, SessionLocal  # noqa: E402


@app.on_event("startup")
def on_startup() -> None:
   Base.metadata.create_all(bind=engine)
   # Mount static for cookies
   try:
       app.mount("/static", StaticFiles(directory="static"), name="static")
   except Exception:
       # Ensure directory exists
       import os
       os.makedirs("static", exist_ok=True)
       app.mount("/static", StaticFiles(directory="static"), name="static")
   # Cleanup expired cookies on startup
   try:
       from app.services.cookie import CookieService
       svc = CookieService(SessionLocal())
       svc.cleanup_expired()
   except Exception:
       pass


# Global auth+activation middleware (whitelist /auth/*, /health, docs)
from datetime import datetime, timezone  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from jose import JWTError, jwt  # noqa: E402

from app.models.account import Account, ActivationStatus, UserRole  # noqa: E402
from app.services.security import expand_uuid  # noqa: E402


@app.middleware("http")
async def enforce_auth_activation(request, call_next):
   path = request.url.path
   method = request.method.upper()

   # Allow preflight CORS
   if method == "OPTIONS":
       return await call_next(request)

   # Whitelist paths: health, docs, redoc, openapi, and specific auth endpoints
   whitelisted_prefixes = ("/health", "/docs")
   whitelisted_exact = {"/openapi.json", "/redoc", "/docs/oauth2-redirect", "/auth/login", "/auth/register"}
   if path.startswith(whitelisted_prefixes) or path in whitelisted_exact:
       return await call_next(request)

   # Enforce bearer token
   auth_header = request.headers.get("Authorization", "")
   if not auth_header.startswith("Bearer "):
       return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
   token = auth_header.split(" ", 1)[1]

   try:
       payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
       sub = payload.get("sub")
       if not sub:
           raise JWTError("missing sub")
       user_id = sub
       if len(sub) <= 24 and all(c.isalnum() or c in "-_" for c in sub):
           try:
               user_id = expand_uuid(sub)
           except Exception:
               user_id = sub
   except JWTError:
       return JSONResponse(status_code=401, content={"detail": "Could not validate credentials"})

   db = SessionLocal()
   try:
       user = db.get(Account, user_id)
       if not user:
           return JSONResponse(status_code=401, content={"detail": "Could not validate credentials"})

       # Admin users bypass activation check
       if user.role != UserRole.admin:
           # Allow not-activated users to call activation endpoint and view /auth/me
           activation_allowed_paths = {"/activation/activate", "/auth/me"}
           if path not in activation_allowed_paths:
               # Activation checks
               if user.activation_status != ActivationStatus.active:
                   return JSONResponse(status_code=403, content={"detail": "Account not activated"})
               if user.expired_time is not None and user.expired_time <= datetime.now(timezone.utc):
                   return JSONResponse(status_code=403, content={"detail": "Activation expired"})

       # Optionally attach current user
       request.state.user = user
       response = await call_next(request)
       return response
   finally:
       db.close()


@app.get("/")
def read_root():
   return {"message": "OK", "name": settings.PROJECT_NAME, "version": settings.VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
