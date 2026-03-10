import os

import google.generativeai as genai
from dotenv import set_key
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import verify_admin
from app.api.v2.system import log_manager
from app.core.paths import PROJECT_ROOT
from app.core.response import BaseResponse, success_response
from app.core.security import get_password_hash
from app.db.migrations import run_db_migrations, run_single_table_migration
from app.db.seeds import seed_initial_data
from app.db.tables import system_settings, users
from app.schemas import (
    AdminSetupConfig,
    DatabaseConfig,
    FirstAdminRequest,
    GeneralConfig,
    LLMConfig,
    NetworkConfig,
    VectorConfig,
)


class MigrationRequest(BaseModel):
    force_reset: bool = False


class SingleTableMigrationRequest(BaseModel):
    table_name: str


router = APIRouter()
DEFAULT_ADMIN_KEY = "gym-food-super-admin"
ENV_PATH = PROJECT_ROOT / ".env"


def save_to_env(config_dict: dict):
    try:
        for key, value in config_dict.items():
            env_key = key.upper()
            set_key(str(ENV_PATH), env_key, str(value), quote_mode="always")
            os.environ[env_key] = str(value)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu file .env: {str(exc)}") from exc


def setup_state_response(setup_status: str, message: str, **extra):
    data = {"setup_status": setup_status, **extra}
    return success_response(data=data, message=message)


@router.get("/status", response_model=BaseResponse[dict])
async def get_system_status():
    current_key = os.getenv("ADMIN_SECRET_KEY", DEFAULT_ADMIN_KEY)
    if current_key == DEFAULT_ADMIN_KEY:
        return setup_state_response(
            "pending",
            "Hệ thống chưa bảo mật (Admin Key mặc định).",
            requires_auth=False,
            step=0,
        )

    api_base = os.getenv("API_BASE_URL")
    if not api_base:
        return setup_state_response(
            "pending",
            "Chưa cấu hình Network (API Base URL).",
            requires_auth=True,
            step=1,
        )

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return setup_state_response(
            "pending",
            "Chưa cấu hình Database.",
            requires_auth=True,
            step=2,
        )

    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)

        if "users" not in inspector.get_table_names():
            return setup_state_response(
                "pending",
                "Chưa khởi tạo cấu trúc bảng (cần migrate).",
                requires_auth=True,
                step=4,
            )

        with engine.connect() as conn:
            if "roles" in inspector.get_table_names() and "user_roles" in inspector.get_table_names():
                admin_count = conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM users u
                        JOIN user_roles ur ON u.id = ur.user_id
                        JOIN roles r ON ur.role_id = r.id
                        WHERE LOWER(r.name) = 'admin'
                        """
                    )
                ).scalar()
            else:
                admin_count = 0

            if admin_count == 0:
                return setup_state_response(
                    "pending",
                    "Chưa có tài khoản Admin (cần tạo).",
                    requires_auth=True,
                    step=4.5,
                )
    except Exception as exc:
        return setup_state_response(
            "pending",
            str(exc),
            requires_auth=True,
            step=2,
        )

    return setup_state_response("completed", "Hệ thống đã sẵn sàng.", requires_auth=True)


@router.post("/init-admin", response_model=BaseResponse[dict])
async def initialize_admin(config: AdminSetupConfig):
    current_key = os.getenv("ADMIN_SECRET_KEY", DEFAULT_ADMIN_KEY)
    if current_key != DEFAULT_ADMIN_KEY:
        raise HTTPException(status_code=400, detail="Admin đã được thiết lập. Không thể khởi tạo lại.")
    if len(config.admin_secret_key) < 8:
        raise HTTPException(status_code=400, detail="Admin Key phải dài ít nhất 8 ký tự.")
    save_to_env({"ADMIN_SECRET_KEY": config.admin_secret_key})
    return success_response(message="Đã tạo Admin Key thành công")


@router.post("/step1/save", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def save_network_config(config: NetworkConfig):
    save_to_env(config.model_dump())
    return success_response(message="Network configuration saved.")


@router.post("/step2/test", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def test_database(config: DatabaseConfig):
    try:
        url = f"postgresql+psycopg://{config.username}:{config.password}@{config.host}:{config.port}/{config.db_name}"
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return success_response(message="Kết nối DB thành công (Driver: Psycopg 3).")
    except Exception as exc:
        err_msg = str(exc)
        if "psycopg" in err_msg.lower():
            err_msg += " (Kiểm tra requirements.txt đã có 'psycopg[binary]' chưa?)"
        raise HTTPException(400, detail=f"Lỗi kết nối DB: {err_msg}") from exc


@router.post("/step2/save", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def save_database_config(config: DatabaseConfig):
    db_url = f"postgresql+psycopg://{config.username}:{config.password}@{config.host}:{config.port}/{config.db_name}"
    save_data = config.model_dump()
    save_data["DATABASE_URL"] = db_url
    save_to_env(save_data)
    return success_response(message="Database configuration saved.")


@router.get("/step4/db-status", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def check_db_status():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(400, "Chưa cấu hình Database.")
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return success_response(
            data={
                "status": "dirty" if tables else "clean",
                "tables": tables,
            },
            message=f"Found {len(tables)} tables." if tables else "Database empty.",
        )
    except Exception as exc:
        raise HTTPException(500, f"Error: {exc}") from exc


@router.post("/step4/db-migrate", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def execute_migration_endpoint(request: MigrationRequest):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(400, "Missing DATABASE_URL.")

    async def ws_log(msg):
        await log_manager.broadcast_log(msg)

    try:
        engine = create_engine(db_url)
        await run_db_migrations(engine, request.force_reset, ws_log)
        await seed_initial_data(engine, ws_log)
        await ws_log("[DONE] System initialization complete!")
        return success_response(message="Database initialized.")
    except Exception as exc:
        await ws_log(f"[ERROR] {str(exc)}")
        raise HTTPException(500, str(exc)) from exc


@router.post("/migrate-table", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def migrate_single_table(request: SingleTableMigrationRequest):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(400, "Missing DATABASE_URL.")

    async def ws_log(msg):
        print(f"[SingleMigrate] {msg}")

    try:
        engine = create_engine(db_url)
        await run_single_table_migration(engine, request.table_name, ws_log)
        return success_response(message=f"Table '{request.table_name}' synced successfully.")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.post("/create-first-admin", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def create_first_admin(data: FirstAdminRequest):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(400, "Chưa cấu hình Database.")

    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            existing_admin = conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM users u
                    JOIN user_roles ur ON u.id = ur.user_id
                    JOIN roles r ON ur.role_id = r.id
                    WHERE LOWER(r.name) = 'admin'
                    """
                )
            ).scalar()

            if existing_admin > 0:
                return success_response(message="Tài khoản Admin đã tồn tại. Bỏ qua bước này.")

            raw_password = data.password
            if len(raw_password.encode("utf-8")) > 72:
                raw_password = raw_password[:72]
            hashed_pw = get_password_hash(raw_password)

            result = conn.execute(
                users.insert().values(
                    username=data.username,
                    email=data.email,
                    password_hash=hashed_pw,
                    full_name=data.full_name,
                    is_active=True,
                ).returning(users.c.id)
            )
            new_user_id = result.scalar()

            admin_role_id = conn.execute(text("SELECT id FROM roles WHERE LOWER(name)='admin'")).scalar()
            if not admin_role_id:
                admin_role_id = conn.execute(
                    text("INSERT INTO roles (name, description) VALUES ('admin', 'Super Admin') RETURNING id")
                ).scalar()

            conn.execute(
                text("INSERT INTO user_roles (user_id, role_id) VALUES (:uid, :rid)"),
                {"uid": new_user_id, "rid": admin_role_id},
            )

        return success_response(message=f"Tài khoản Admin '{data.username}' đã được tạo thành công.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo Admin: {str(exc)}") from exc


@router.post("/step3/test", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def test_vector_db(config: VectorConfig):
    try:
        client = QdrantClient(url=config.host, api_key=config.api_key, timeout=5)
        collections = client.get_collections().collections
        exists = any(collection.name == config.collection_name for collection in collections)
        return success_response(
            data={
                "collection_exists": exists,
                "state": "success" if exists else "warning",
            },
            message=(
                f"Connected! Collection '{config.collection_name}' found."
                if exists
                else "Connected, but collection not found."
            ),
        )
    except Exception as exc:
        raise HTTPException(400, f"Qdrant connection failed: {str(exc)}") from exc


@router.post("/step3/save", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def save_vector_config(config: VectorConfig):
    try:
        url_parts = config.host.replace("http://", "").replace("https://", "").split(":")
        host = url_parts[0]
        port = url_parts[1] if len(url_parts) > 1 else "6333"
        save_to_env({
            "QDRANT_HOST": host,
            "QDRANT_PORT": port,
            "COLLECTION_NAME": config.collection_name,
        })
        return success_response(message="Vector DB config saved.")
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.post("/step4/test", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def test_llm_connection(config: LLMConfig):
    try:
        genai.configure(api_key=config.api_key)
        model = genai.GenerativeModel(config.model_name)
        response = model.generate_content("Hello")
        if response.text:
            return success_response(message="LLM connected successfully.")
        raise ValueError("Empty response")
    except Exception as exc:
        raise HTTPException(400, f"LLM Failed: {str(exc)}") from exc


@router.post("/step4/save", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def save_llm_config(config: LLMConfig):
    save_to_env(
        {
            "LLM_BACKEND": config.provider,
            "GOOGLE_API_KEY": config.api_key,
            "GEMINI_MODEL": config.model_name,
        }
    )
    return success_response(message="LLM credentials saved.")


@router.post("/step5/save", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def save_general_config(config: GeneralConfig):
    try:
        save_to_env(config.model_dump())
    except Exception as exc:
        print(f"Canh bao: Khong luu duoc vao .env: {exc}")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return success_response(message="Đã lưu vào .env, nhưng chưa kết nối DB để lưu bảng settings.")

    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            for key, value in config.model_dump().items():
                stmt = insert(system_settings).values(key=key, value=str(value))
                do_update_stmt = stmt.on_conflict_do_update(
                    index_elements=["key"],
                    set_=dict(value=str(value)),
                )
                conn.execute(do_update_stmt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu DB: {str(exc)}") from exc

    return success_response(message="Cấu hình đã được lưu đồng bộ (file + database).")
