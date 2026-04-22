from __future__ import annotations

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent


class IntentPromptMixin:
    def _build_prompt(
        self,
        profile: dict,
        request: NutritionRecommendationRequest,
        base_intent: NutritionIntent,
    ) -> str:
        return f"""
Bạn là bộ phân tích ý định dinh dưỡng cho một meal planner có tính quyết định.
Nhiệm vụ là hiểu đúng ý người dùng, không tạo thực đơn, không tự tính gram, calories hay macros.
Ưu tiên thông tin người dùng nói trong request hiện tại nếu nó bổ sung hoặc ghi đè profile đang lưu.
Chỉ trả về JSON, không thêm giải thích ngoài JSON.

Hệ thống có 2 tầng goal:
1. goal_raw_semantic: giữ ý nghĩa tự nhiên mà người dùng đang nói.
2. goal_normalized_internal: ánh xạ ý nghĩa đó về nhóm goal nội bộ mà planner hỗ trợ.

Allowed goal_raw_semantic:
- gain_weight_general
- gain_muscle
- lose_weight_general
- fat_loss
- maintain
- eat_healthier
- support_training
- null

Allowed goal_normalized_internal:
- gain_muscle
- lose_weight
- maintain
- null

Allowed planning_strategy:
- surplus_balanced
- surplus_high_protein
- deficit_balanced
- deficit_high_satiety
- maintenance_balanced
- maintenance_health_support
- maintenance_training_support
- null

Allowed priorities:
- protein
- satiety
- recovery
- simplicity
- budget
- variety
- lightness
- micronutrients
- digestion

Allowed dietary_preference:
- omnivore
- vegetarian
- vegan
- pescatarian
- null

Allowed cooking_complexity:
- easy
- medium
- any
- null

Allowed budget_level:
- low
- medium
- high
- null

Allowed meal_style:
- simple
- traditional
- high_protein
- light
- balanced
- null

Allowed satiety_preference:
- high
- normal
- light
- null

Quy tắc bắt buộc:
- Nếu người dùng nói "tăng cân", "lên cân", hoặc "gain weight", hãy map về goal_normalized_internal="gain_muscle" vì planner chỉ hỗ trợ gain_muscle, lose_weight, maintain.
- Allergies phải dùng nhãn chuẩn: dairy, egg, soy, peanut, tree_nut, gluten, shellfish, fish, sesame.
- Danh sách food/preference phải ngắn và chỉ chứa thứ người dùng nói rõ.
- Nếu người dùng nói "tránh", "không ăn", "avoid", hãy đưa vào must_avoid, không đưa vào allergies, trừ khi người dùng nói rõ đó là dị ứng hoặc không dung nạp.
- Nếu người dùng nói "không bị đói", "no lâu", hãy set satiety_preference="high" và thêm priority="satiety".
- Nếu người dùng nói "sau tập", "post workout", hãy set post_workout_meal=true và thêm priority="recovery".
- Không được tự bịa món ăn hay sở thích mà người dùng không nhắc tới.
- Không được lặp cùng một food ở nhiều trường must_include, preferred_foods, disliked_foods, must_avoid.
- Nếu instruction chỉ nói về style, độ tiện, hoặc cách nấu, hãy giữ goal từ base intent.
- confidence chỉ nên cao khi instruction thật sự rõ nghĩa.

Quy tắc semantic normalization:
- "tăng cân", "lên cân", "gain weight" -> goal_raw_semantic="gain_weight_general"
- "tăng cơ", "bulk", "muscle gain" -> goal_raw_semantic="gain_muscle"
- "giảm cân", "xuống cân" -> goal_raw_semantic="lose_weight_general"
- "giảm mỡ", "fat loss", "cutting" -> goal_raw_semantic="fat_loss"
- "ăn lành mạnh", "ăn khỏe hơn" -> goal_raw_semantic="eat_healthier"
- "ăn để tập tốt hơn", "hỗ trợ tập luyện", "post workout" -> goal_raw_semantic="support_training"
- gain_weight_general thường map sang goal_normalized_internal="gain_muscle" với planning_strategy="surplus_balanced"
- gain_muscle map sang goal_normalized_internal="gain_muscle" với planning_strategy="surplus_high_protein"
- lose_weight_general map sang goal_normalized_internal="lose_weight" với planning_strategy="deficit_balanced"
- fat_loss map sang goal_normalized_internal="lose_weight" với planning_strategy="deficit_high_satiety"
- eat_healthier map sang goal_normalized_internal="maintain" với planning_strategy="maintenance_health_support"
- support_training map sang goal_normalized_internal="maintain" với planning_strategy="maintenance_training_support"

Ví dụ A
Instruction: "giảm mỡ nhưng không bị đói, dễ nấu, tránh đồ chiên"
Output:
{{
  "goal_raw_semantic": "fat_loss",
  "goal_normalized_internal": "lose_weight",
  "planning_strategy": "deficit_high_satiety",
  "goal": "lose_weight",
  "priorities": ["satiety", "simplicity"],
  "hard_constraints": {{"dietary_preference": null, "allergies": [], "must_avoid": ["đồ chiên"]}},
  "soft_preferences": {{"must_include": [], "preferred_foods": [], "disliked_foods": [], "cooking_complexity": "easy", "budget_level": null, "meal_style": null}},
  "meal_preferences": {{"meal_count": null, "pre_workout_meal": false, "post_workout_meal": false, "late_dinner": false, "satiety_preference": "high"}},
  "notes": [],
  "confidence": 0.86
}}

Ví dụ B
Instruction: "ăn chay, tránh sữa và lạc, 4 bữa mỗi ngày"
Output:
{{
  "goal_raw_semantic": null,
  "goal_normalized_internal": null,
  "planning_strategy": null,
  "goal": null,
  "priorities": [],
  "hard_constraints": {{"dietary_preference": "vegetarian", "allergies": [], "must_avoid": ["sữa", "lạc"]}},
  "soft_preferences": {{"must_include": [], "preferred_foods": [], "disliked_foods": [], "cooking_complexity": null, "budget_level": null, "meal_style": null}},
  "meal_preferences": {{"meal_count": 4, "pre_workout_meal": false, "post_workout_meal": false, "late_dinner": false, "satiety_preference": null}},
  "notes": [],
  "confidence": 0.84
}}

Ví dụ C
Instruction: "tăng cân"
Output:
{{
  "goal_raw_semantic": "gain_weight_general",
  "goal_normalized_internal": "gain_muscle",
  "planning_strategy": "surplus_balanced",
  "goal": "gain_muscle",
  "priorities": ["protein"],
  "hard_constraints": {{"dietary_preference": null, "allergies": [], "must_avoid": []}},
  "soft_preferences": {{"must_include": [], "preferred_foods": [], "disliked_foods": [], "cooking_complexity": null, "budget_level": null, "meal_style": null}},
  "meal_preferences": {{"meal_count": null, "pre_workout_meal": false, "post_workout_meal": false, "late_dinner": false, "satiety_preference": null}},
  "notes": ["mapped_gain_weight_to_surplus_balanced"],
  "confidence": 0.80
}}

Stored profile:
{profile}

Current request:
{request.model_dump(exclude_none=True)}

Base intent draft:
{base_intent.model_dump(mode="json")}

Trả JSON đúng shape sau:
{{
  "goal_raw_semantic": null,
  "goal_normalized_internal": null,
  "planning_strategy": null,
  "goal": null,
  "priorities": [],
  "hard_constraints": {{
    "dietary_preference": null,
    "allergies": [],
    "must_avoid": []
  }},
  "soft_preferences": {{
    "must_include": [],
    "preferred_foods": [],
    "disliked_foods": [],
    "cooking_complexity": null,
    "budget_level": null,
    "meal_style": null
  }},
  "meal_preferences": {{
    "meal_count": null,
    "pre_workout_meal": false,
    "post_workout_meal": false,
    "late_dinner": false,
    "satiety_preference": null
  }},
  "notes": [],
  "confidence": 0.0
}}
""".strip()

    def _build_chat_clarification_question(self, raw_goal: str | None) -> str | None:
        questions = {
            "gain_weight_general": "Bạn muốn tăng cân theo hướng tăng cơ, hay chỉ muốn tăng cân nói chung?",
            "lose_weight_general": "Bạn muốn giảm cân nói chung, hay ưu tiên giảm mỡ nhưng vẫn no lâu?",
            "eat_healthier": "Bạn muốn ăn lành mạnh theo hướng nào: dễ duy trì hằng ngày, kiểm soát cân nặng, hay hỗ trợ tập luyện?",
        }
        return questions.get(raw_goal)
