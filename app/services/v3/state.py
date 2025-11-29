from typing import Annotated, TypedDict,List
from langgraph.graph.message import add_messages

# State của Agent: Đơn giản là một danh sách tin nhắn được cộng dồn
class AgentState(TypedDict):
    messages: Annotated[List, add_messages]