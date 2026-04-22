import os
try:
    from langgraph.checkpoint.redis.aio import AsyncRedisSaver
except ImportError:
    from langgraph.checkpoint.redis import AsyncRedisSaver

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.services.v3.state import AgentState
from app.services.v3.tools import agent_tools
from app.api.v2.chat_v2 import HARDCORE_SYSTEM_PROMPT 
from app.core.config import settings
# Dùng port 6380 như đã thống nhất để tránh xung đột
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class GymAgentV3:
    def __init__(self):
        # 1. Setup Redis Checkpointer
        self.checkpointer = AsyncRedisSaver(redis_url=REDIS_URL)

        # 2. Setup LLM
        self.llm = ChatOllama(
            model="qwen2.5:3b", 
            temperature=0, 
            keep_alive="5m"
        )
        # self.llm = ChatGoogleGenerativeAI(
        #     model=settings.GEMINI_MODEL,
        #     google_api_key=settings.GOOGLE_API_KEY,
        #     temperature=0.3,
        #     convert_system_message_to_human=True
        # )
        self.llm_with_tools = self.llm.bind_tools(tools=agent_tools)

        # 3. Build Graph
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", ToolNode(agent_tools))

        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", tools_condition)
        workflow.add_edge("tools", "agent")

        self.app = workflow.compile(checkpointer=self.checkpointer)

    # --- [THÊM HÀM NÀY] ---
    async def initialize(self):
        """
        Hàm này bắt buộc phải chạy 1 lần khi server start
        để tạo các Index (Mục lục) trong Redis Stack.
        """
        print("⚡ [Redis] Đang khởi tạo Search Index...")
        await self.checkpointer.setup()
        print("✅ [Redis] Search Index đã sẵn sàng!")
    # ----------------------

    async def call_model(self, state: AgentState):
        messages = state["messages"]
        user_profile = state.get("user_profile", {})
        
        # 1. Tạo System Prompt động với User Context
        dynamic_system = HARDCORE_SYSTEM_PROMPT + "\n\n[USER CONTEXT]\n"
        if user_profile:
            dynamic_system += f"- Độ tuổi: {user_profile.get('age', 'N/A')}\n"
            dynamic_system += f"- Cân nặng: {user_profile.get('weight', 'N/A')} kg\n"
            dynamic_system += f"- Mục tiêu: {user_profile.get('target_goal', 'Duy trì')}\n"
            dynamic_system += f"- Dị ứng: {user_profile.get('allergies', 'Không')}\n"
            dynamic_system += f"- Chế độ ăn ưu tiên: {user_profile.get('dietary_preference', 'Bình tĩnh')}\n"
            if 'tdee' in user_profile:
                dynamic_system += f"- Tổng Calo tiêu hao (TDEE): {user_profile['tdee']} kcal\n"
            if 'macros' in user_profile:
                m = user_profile['macros']
                dynamic_system += f"- Macro tối ưu/ngày: {m.get('calories')} kcal, Đạm: {m.get('protein')}g, Carb: {m.get('carbs')}g, Béo: {m.get('fat')}g\n"
        
        # 2. Xử lý System Message
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=dynamic_system)] + messages
        else:
            # Ghi đè SystemMessage cũ bằng phiên bản mới nhất
            messages[0] = SystemMessage(content=dynamic_system)
        
        response = await self.llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def process_question(self, session_id: str, question: str, user_dict: dict = None):
        if user_dict is None:
            user_dict = {}
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": 10
        }
        input_msg = HumanMessage(content=question)
        
        try:
            final_state = await self.app.ainvoke(
                {
                    "messages": [input_msg],
                    "user_profile": user_dict
                }, 
                config=config
            )
            return final_state["messages"][-1].content
        except Exception as e:
            if "recursion" in str(e).lower():
                return "Xin lỗi bạn, yêu cầu cân bằng dinh dưỡng này quá phức tạp và tôi không thể tìm được cấu trúc thực đơn tối ưu trong thời gian giới hạn. Hãy thử nới lỏng các yêu cầu (VD: Không cần chính xác 100% macro) hoặc hỏi một câu khác nhé!"
            raise e

# Singleton Instance
# agent_service_v3 = GymAgentV3()
agent_service_v3 = None # Placeholder to prevent ImportErrors if imported elsewhere