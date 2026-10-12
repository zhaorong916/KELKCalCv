"""FastAPI 应用入口"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.api import projects, valves, calculations, fluids, units, valve_types, nominal_sizes, public_options, pipe_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：确保表结构存在并初始化介质库 / 单位字典
    from app.core.database import Base, engine
    from app.models import Fluid
    from app.calc.properties import get_fluid_defaults
    from app.calc.units import seed_unit_definitions
    from app.core.database import SessionLocal
    Base.metadata.create_all(bind=engine, checkfirst=True)
    with SessionLocal() as db:
        if db.query(Fluid).count() == 0:
            for item in get_fluid_defaults():
                db.add(Fluid(**item))
            db.commit()
        # 单位字典初始化（若表为空则从内置种子注入）
        seed_unit_definitions(db)
        # KELK 阀门产品系列初始化
        valve_types.seed_valve_types(db)
        # 筛选器配置初始化 (公称通径/阀芯尺寸)
        valve_types.seed_valve_filter_config(db)
        # 公称尺寸对照表初始化
        nominal_sizes.seed_nominal_sizes(db)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS if isinstance(settings.BACKEND_CORS_ORIGINS, list) else [settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = settings.API_V1_PREFIX
app.include_router(projects.router, prefix=PREFIX)
app.include_router(valves.router, prefix=PREFIX)
app.include_router(calculations.router, prefix=PREFIX)
app.include_router(fluids.router, prefix=PREFIX)
app.include_router(units.router, prefix=PREFIX)
app.include_router(valve_types.router, prefix=PREFIX)
app.include_router(nominal_sizes.router, prefix=PREFIX)
app.include_router(public_options.router, prefix=PREFIX)
app.include_router(pipe_data.router, prefix=PREFIX)


@app.get("/")
def root():
    # 如果有前端静态文件，返回 index.html (SPA 入口)
    _idx = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "index.html")
    if os.path.isfile(_idx):
        return FileResponse(_idx)
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


@app.get(f"{PREFIX}/health")
def health():
    return {"status": "ok"}


# ========== 静态文件服务 (前端 SPA) ==========
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_static_dir):
    # 挂载 assets 目录
    _assets_dir = os.path.join(_static_dir, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    # SPA fallback: 所有非 /api 路由返回 index.html
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str, request: Request):
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
        file_path = os.path.join(_static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_static_dir, "index.html"))
