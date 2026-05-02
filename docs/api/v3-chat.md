# Chat V3 Endpoints

> Updated: 2026-05-02
> Source code: `app/api/v3/chat_v3.py`

## Overview

Chat V3 is now active as a safe general-chat endpoint. It is intentionally not a
meal-plan generator. Personalized meal recommendations must go through
`/api/v3/nutrition/recommendation-agent`, where `NutritionWorkflowService`
performs macro calculation, retrieval, validation, and safety checks.

The old placeholder LangGraph agent under `app/services/v3/agent.py` is not
mounted because it exposes legacy tools that can bypass the production
recommendation contract.

## Endpoint

### POST `/api/v3/chat`

Permission: `chat.use`

Request:

```json
{
  "question": "TDEE la gi?",
  "session_id": null
}
```

Response:

```json
{
  "status": "success",
  "data": {
    "answer": "TDEE la tong nang luong co the ban tieu hao trong mot ngay...",
    "session_id": "uuid-...",
    "engine": "GeneralChatService+ollama",
    "status": "answered",
    "context_used": ["general nutrition education"],
    "suggested_endpoint": null
  }
}
```

If the user asks for a concrete meal plan, the endpoint returns a routing
contract instead of generating food items:

```json
{
  "status": "success",
  "data": {
    "answer": "Yeu cau nay can engine recommendation...",
    "session_id": "uuid-...",
    "engine": "GeneralChatRouter",
    "status": "use_nutrition_agent",
    "context_used": ["NutritionWorkflowService required"],
    "suggested_endpoint": "/api/v3/nutrition/recommendation-agent"
  }
}
```

Frontend should render `data.answer`. When `data.status` is
`use_nutrition_agent`, call `data.suggested_endpoint` with a structured
nutrition request instead of treating the chat response as a meal plan.

## Safety Boundary

- Chat V3 may explain general nutrition concepts.
- Chat V3 must not produce final meal plans, shopping lists, or specific food
  item selections.
- The recommendation agent remains the only public endpoint for personalized
  meal plans.
- Final foods must still come from the validated core recommendation response.
