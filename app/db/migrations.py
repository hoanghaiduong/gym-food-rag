from sqlalchemy import create_engine, text as sql_text, inspect
from sqlalchemy.schema import CreateColumn
from sqlalchemy.ext.compiler import compiles
from app.db.tables import metadata  # Đảm bảo đúng tên file schema của bạn

async def run_db_migrations(engine, force_reset: bool = False, log_func=None):
    """
    Hệ thống Migration thông minh: Tự động đồng bộ cấu trúc Python -> Database.
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

    # 2. Tạo các bảng chưa tồn tại (Cơ bản)
    await log("🔍 Checking tables...")
    metadata.create_all(engine)
    
    # 3. [NÂNG CẤP] AUTO-MIGRATE: Tự động phát hiện và thêm cột thiếu
    await log("🔄 Syncing columns (Auto-Migration)...")
    
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Dùng transaction để đảm bảo an toàn
    with engine.begin() as conn:
        # Duyệt qua từng bảng được định nghĩa trong Code Python
        for table_name, table_obj in metadata.tables.items():
            
            # Nếu bảng đã tồn tại trong DB, ta kiểm tra cột
            if table_name in existing_tables:
                # Lấy danh sách cột hiện có trong DB
                db_columns = [col['name'] for col in inspector.get_columns(table_name)]
                
                # Duyệt qua từng cột trong Code Python
                for column in table_obj.columns:
                    # Nếu cột trong code chưa có trong DB -> Thêm ngay
                    if column.name not in db_columns:
                        await log(f"   ➕ Detected missing column: {table_name}.{column.name}")
                        
                        # Magic: Tự động tạo câu lệnh SQL đúng chuẩn loại dữ liệu
                        # column.type.compile(engine.dialect) sẽ tự biến String -> VARCHAR, etc.
                        col_type = column.type.compile(engine.dialect)
                        
                        # Xử lý nullable (Mặc định thêm cột mới nên để NULL để tránh lỗi dữ liệu cũ)
                        # Nếu muốn NOT NULL, bạn phải set default value, ở đây ta đơn giản hóa
                        alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}"
                        
                        try:
                            conn.execute(sql_text(alter_stmt))
                            await log(f"      ✅ Added column '{column.name}' successfully.")
                        except Exception as e:
                            await log(f"      ❌ Failed to add column '{column.name}': {e}")

    await log("🎉 Database synchronization complete.")