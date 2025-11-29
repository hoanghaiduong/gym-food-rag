import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from app.core.v3.langgraph_redis import AsyncRedisSaver
from app.services.v3.state import AgentState
from app.services.v3.tools import agent_tools
from app.core.config import settings
from app.api.v2.chat_v2 import HARDCORE_SYSTEM_PROMPT 

# [QUAN TRỌNG] Import Checkpointer Redis vừa tạo


class GymAgentV3:
    def __init__(self):
        # 1. Setup Redis Checkpointer
        # Mỗi khi Agent chạy xong 1 bước, nó sẽ tự lưu vào Redis
        self.checkpointer = AsyncRedisSaver()

        # 2. Setup LLM
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.3,
            convert_system_message_to_human=True
        )
        self.llm_with_tools = self.llm.bind_tools(tools=agent_tools)

        # 3. Xây dựng Graph
        workflow = StateGraph(AgentState)
        
        # Nodes
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", ToolNode(agent_tools))

        # Edges
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            tools_condition, # Tự động sang 'tools' nếu LLM muốn gọi hàm
        )
        workflow.add_edge("tools", "agent") # Chạy tool xong quay lại agent

        # [QUAN TRỌNG] Compile với Redis Checkpointer
        self.app = workflow.compile(checkpointer=self.checkpointer)

    def call_model(self, state: AgentState):
        messages = state["messages"]
        
        # Inject System Prompt nếu chưa có (Chỉ làm 1 lần đầu tiên của session)
        # Kiểm tra xem message đầu tiên có phải SystemMessage không
        if not messages or not isinstance(messages[0], SystemMessage):
            system_msg = SystemMessage(content=HARDCORE_SYSTEM_PROMPT)
            # Chèn vào đầu list gửi đi (không sửa state gốc để tránh duplicate)
            messages = [system_msg] + messages
        
        response = self.llm_with_tools.invoke(messages)
        return {"messages": [response]}

    async def process_question(self, session_id: str, question: str,db_session=None):
        """
        Hàm chạy chính.
        """
        # Config thread_id là Session ID để Redis biết đang nói chuyện với ai
        config = {"configurable": {"thread_id": session_id}}
        
        input_message = HumanMessage(content=question)
        
        # Chạy Graph (Toàn bộ trạng thái sẽ được tự động Load/Save từ Redis)
        async for event in self.app.astream({"messages": [input_message]}, config=config):
            pass 
            
        # Lấy kết quả cuối cùng từ State hiện tại
        snapshot = await self.app.aget_state(config)
        if not snapshot.values:
             return "Xin lỗi, hệ thống đang bận."

        final_msg = snapshot.values["messages"][-1]
        
        # Trả về nội dung text
        return final_msg.content

# Singleton Instance
agent_service_v3 = GymAgentV3()