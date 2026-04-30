from __future__ import annotations

from typing import Any


class NutritionAgentExplanationBuilder:
    def build(
        self,
        *,
        status: str,
        recommendation: dict[str, Any] | None,
        clarification: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> str:
        if clarification:
            return str(clarification.get("question") or "Mình cần thêm thông tin để tạo thực đơn chính xác.")
        if error:
            return f"Không thể tạo khuyến nghị do lỗi hệ thống: {error}"
        if not recommendation:
            return "Chưa có thực đơn hợp lệ để trả về."

        validation = recommendation.get("validation") or {}
        if status != "validated" or not bool(validation.get("passed")):
            issues = validation.get("issues") or []
            issue_codes = [str(item.get("code")) for item in issues[:3] if isinstance(item, dict)]
            suffix = f" Các lỗi chính: {', '.join(issue_codes)}." if issue_codes else ""
            return "Core engine chưa tạo được thực đơn đạt ràng buộc nên agent không trả final plan." + suffix

        plan = recommendation.get("plan") or {}
        totals = validation.get("totals") or recommendation.get("totals") or {}
        summary = str(plan.get("summary") or "Đã tạo thực đơn phù hợp với hồ sơ dinh dưỡng.")
        calories = totals.get("energy_kcal")
        protein = totals.get("protein_g")
        carbs = totals.get("carbs_g")
        fat = totals.get("fat_g")
        if calories is None:
            return summary
        return (
            f"{summary} Thực đơn đã qua kiểm tra ràng buộc, "
            f"ước tính {round(float(calories), 1)} kcal, "
            f"protein {round(float(protein or 0), 1)}g, "
            f"carb {round(float(carbs or 0), 1)}g, "
            f"fat {round(float(fat or 0), 1)}g."
        )
