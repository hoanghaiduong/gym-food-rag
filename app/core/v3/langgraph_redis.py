import pickle
from typing import Any, Optional, AsyncIterator,List,Tuple
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from redis.asyncio import Redis
from app.core.config import settings

class AsyncRedisSaver(BaseCheckpointSaver):
    """
    Custom Checkpointer: Lưu trạng thái của Agent vào Redis.
    Giúp Bot 'nhớ' được ngữ cảnh câu chuyện giữa các request.
    """
    def __init__(self):
        super().__init__()
        self.client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=False # Bắt buộc False để lưu bytes (pickle)
        )
    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: List[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        Lưu các dữ liệu ghi trung gian (Required by LangGraph mới).
        Đối với Chatbot cơ bản không cần resume phức tạp, ta có thể để trống (pass)
        để tránh lỗi NotImplementedError.
        """
        pass
    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> RunnableConfig:
        """Ghi state vào Redis"""
        thread_id = config["configurable"]["thread_id"]
        
        # Serialize object thành bytes
        data = pickle.dumps({
            "checkpoint": checkpoint,
            "metadata": metadata,
            "versions": new_versions
        })
        
        # Lưu với key "checkpoint:{session_id}"
        # TTL: Tự động xóa sau 7 ngày (604800 giây) để dọn rác
        await self.client.set(f"checkpoint:{thread_id}", data, ex=604800)
        
        return config

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Đọc state từ Redis"""
        thread_id = config["configurable"]["thread_id"]
        data = await self.client.get(f"checkpoint:{thread_id}")
        
        if not data:
            return None
            
        saved_data = pickle.loads(data)
        return CheckpointTuple(
            config, 
            saved_data["checkpoint"], 
            saved_data["metadata"], 
            (None, None), # parent_config (bỏ qua)
            [] # pending_writes (bỏ qua)
        )

    async def alist(self, config: RunnableConfig, *, filter: dict[str, Any] | None = None, before: RunnableConfig | None = None, limit: int | None = None) -> AsyncIterator[CheckpointTuple]:
        """Hàm liệt kê (Chưa cần thiết cho Chatbot cơ bản)"""
        yield None