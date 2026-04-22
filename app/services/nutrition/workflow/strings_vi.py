from __future__ import annotations

from typing import Any

from app.services.nutrition_knowledge_service import ascii_normalize, safe_float


DEFAULT_ITEM_REASON = "Được chọn bởi bộ tối ưu dinh dưỡng xác định."
LLM_GENERATION_FAILED_SUMMARY = "Sinh thực đơn bằng LLM thất bại."
INVALID_MODEL_OUTPUT_SUMMARY = "Đầu ra của mô hình không hợp lệ."
MEAL_REALISM_ADD_PROTEIN_REASON = "Bổ sung nguồn đạm để bữa chính thực tế hơn."
MEAL_REALISM_ADD_STAPLE_REASON = "Bổ sung món nền để bữa ăn cân bằng và dễ áp dụng hơn."
RAW_FOOD_KEYWORD = "sống"


def goal_label_vi(goal: str | None) -> str:
    return {
        "gain_muscle": "tăng cơ",
        "lose_weight": "giảm mỡ",
        "maintain": "duy trì",
    }.get(goal or "maintain", "duy trì")


def goal_context_label_vi(raw_goal: Any, resolved_goal: str | None) -> str:
    normalized_raw_goal = ascii_normalize(raw_goal or "").replace(" ", "_")
    if normalized_raw_goal == "gain_weight_general":
        return "tăng cân"
    if normalized_raw_goal == "gain_muscle":
        return "tăng cơ"
    if normalized_raw_goal == "lose_weight_general":
        return "giảm cân"
    if normalized_raw_goal == "fat_loss":
        return "giảm mỡ"
    if normalized_raw_goal == "eat_healthier":
        return "ăn lành mạnh hơn"
    if normalized_raw_goal == "support_training":
        return "hỗ trợ tập luyện"
    return goal_label_vi(resolved_goal)


def build_default_summary(goal_label: str, totals: dict[str, Any]) -> str:
    return (
        f"Thực đơn được tối ưu theo hướng xác định cho mục tiêu {goal_label} với "
        f"{round(safe_float(totals.get('energy_kcal')), 1)} kcal, "
        f"{round(safe_float(totals.get('protein_g')), 1)}g protein, "
        f"{round(safe_float(totals.get('carbs_g')), 1)}g carbohydrate và "
        f"{round(safe_float(totals.get('fat_g')), 1)}g chất béo."
    )


def build_default_reasoning(goal_label: str, totals: dict[str, Any]) -> list[str]:
    return [
        f"Thực đơn được tối ưu theo cơ chế xác định cho mục tiêu {goal_label} thay vì phụ thuộc hoàn toàn vào sinh tự do.",
        (
            f"Tổng dinh dưỡng trong ngày là {round(safe_float(totals.get('energy_kcal')), 1)} kcal, "
            f"{round(safe_float(totals.get('protein_g')), 1)}g protein, "
            f"{round(safe_float(totals.get('carbs_g')), 1)}g carbohydrate và "
            f"{round(safe_float(totals.get('fat_g')), 1)}g chất béo."
        ),
        "Các thực phẩm được chọn từ kho tri thức chuẩn hóa và đã được kiểm tra theo chế độ ăn, dị ứng và các ràng buộc định lượng.",
    ]


def build_default_meal_explanation(
    meal_name: str,
    goal_label: str,
    totals: dict[str, Any],
    top_items: str,
) -> str:
    return (
        f"{meal_name or 'Bữa ăn'} hỗ trợ mục tiêu {goal_label} với "
        f"{round(safe_float(totals.get('energy_kcal')), 1)} kcal và "
        f"{round(safe_float(totals.get('protein_g')), 1)}g protein. "
        f"Thực phẩm chính: {top_items}."
    )
