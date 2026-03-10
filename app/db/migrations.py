from sqlalchemy import create_engine, text as sql_text, inspect
from sqlalchemy.schema import CreateColumn
from sqlalchemy.ext.compiler import compiles
from app.db.tables import metadata  # Đảm bảo đúng tên file schema của bạn

async def sync_table_columns(engine, table_name, table_obj, log_func):
    """
    Logic đồng bộ cột cho 1 bảng cụ thể.
    """
    async def log(msg):
        if log_func: await log_func(msg)

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Nếu bảng chưa tồn tại -> Create
    if table_name not in existing_tables:
        await log(f"🛠 Creating table '{table_name}'...")
        table_obj.create(engine)
        await log(f"✅ Table '{table_name}' created.")
        return

    # Nếu bảng đã tồn tại -> Check Columns
    db_columns = [col['name'] for col in inspector.get_columns(table_name)]

    with engine.begin() as conn:
        for column in table_obj.columns:
            if column.name not in db_columns:
                await log(f"   ➕ Detected missing column: {table_name}.{column.name}")
                
                col_type = column.type.compile(engine.dialect)
                alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}"
                
                try:
                    conn.execute(sql_text(alter_stmt))
                    await log(f"      ✅ Added column '{column.name}' successfully.")
                except Exception as e:
                    await log(f"      ❌ Failed to add column '{column.name}': {e}")

async def run_db_migrations(engine, force_reset: bool = False, log_func=None):
    """
    Hệ thống Migration thông minh: Tự động đồng bộ cấu trúc Python -> Database (ALL TABLES).
    """
    async def log(msg):
        if log_func: await log_func(msg)

    # 1. Xử lý Reset (Xóa sạch làm lại)
    if force_reset:
        await log("⚠️ User requested FORCE RESET. Dropping schema 'public'...")
        with engine.connect() as conn:
            conn.execute(sql_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            conn.commit()
        await log("✅ Schema cleaned.")

    await log("🔄 Syncing ALL tables...")
    
    # Duyệt qua từng bảng được định nghĩa trong Code Python
    for table_name, table_obj in metadata.tables.items():
        await sync_table_columns(engine, table_name, table_obj, log_func)

    await log("🎉 Database synchronization complete.")

async def run_single_table_migration(engine, table_name: str, log_func=None):
    """
    Chạy migration cho RIÊNG 1 BẢNG.
    """
    async def log(msg):
        if log_func: await log_func(msg)

    if table_name not in metadata.tables:
        await log(f"❌ Table '{table_name}' not found in Python definitions.")
        raise ValueError(f"Table '{table_name}' not defined in metadata.")

    table_obj = metadata.tables[table_name]
    await log(f"🔄 Syncing Single Table: {table_name}...")
    await sync_table_columns(engine, table_name, table_obj, log_func)
    await log(f"✅ Table '{table_name}' sync complete.")