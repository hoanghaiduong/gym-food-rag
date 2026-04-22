from typing import Annotated, TypedDict, List, Dict, Any
from langgraph.graph.message import add_messages

# State của Agent: Lưu lịch sử chat và context của user
class AgentState(TypedDict):
    messages: Annotated[List, add_messages]
    user_profile: Dict[str, Any]