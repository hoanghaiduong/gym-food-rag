import numpy as np
import scipy.optimize as opt
from typing import Dict, List, Optional


class NutritionService:
    @staticmethod
    def calculate_tdee(age: int, gender: str, weight: float, height: float, activity_level: str) -> float:
        """
        Tính TDEE (Total Daily Energy Expenditure) bằng công thức Mifflin-St Jeor.
        weight: kg
        height: cm
        age: years
        """
        if gender.lower() == "male":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

        activity_multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9,
        }
        multiplier = activity_multipliers.get(activity_level.lower(), 1.2)
        return bmr * multiplier

    @staticmethod
    def get_macro_targets(
        tdee: float,
        goal: str,
        dietary_preference: str = "omnivore",
        weight: Optional[float] = None,
        strategy: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Phân bổ macro dựa trên goal family nội bộ và planning strategy.
        Strategy là tín hiệu điều hướng chính; goal giữ vai trò fallback để
        tương thích với planner cũ.
        """
        goal = (goal or "maintain").strip().lower()
        diet_key = (dietary_preference or "omnivore").strip().lower()
        strategy = (strategy or "").strip().lower()

        strategy_profiles = {
            "surplus_balanced": {
                "calories": lambda value: value + 220,
                "protein_g_per_kg": {"omnivore": 1.6, "vegetarian": 1.3, "vegan": 1.3, "pescatarian": 1.5},
                "carb_ratio": 0.62,
            },
            "surplus_high_protein": {
                "calories": lambda value: value + 300,
                "protein_g_per_kg": {"omnivore": 1.8, "vegetarian": 1.6, "vegan": 1.6, "pescatarian": 1.7},
                "carb_ratio": 0.65,
            },
            "deficit_balanced": {
                "calories": lambda value: max(value - 350, value * 0.82),
                "protein_g_per_kg": {"omnivore": 1.8, "vegetarian": 1.3, "vegan": 1.3, "pescatarian": 1.6},
                "carb_ratio": 0.58,
            },
            "deficit_high_satiety": {
                "calories": lambda value: max(value - 500, value * 0.75),
                "protein_g_per_kg": {"omnivore": 2.0, "vegetarian": 1.4, "vegan": 1.4, "pescatarian": 1.8},
                "carb_ratio": 0.55,
            },
            "maintenance_balanced": {
                "calories": lambda value: value,
                "protein_g_per_kg": {"omnivore": 1.4, "vegetarian": 1.2, "vegan": 1.2, "pescatarian": 1.3},
                "carb_ratio": 0.60,
            },
            "maintenance_health_support": {
                "calories": lambda value: value,
                "protein_g_per_kg": {"omnivore": 1.3, "vegetarian": 1.15, "vegan": 1.15, "pescatarian": 1.25},
                "carb_ratio": 0.57,
            },
            "maintenance_training_support": {
                "calories": lambda value: value + 80,
                "protein_g_per_kg": {"omnivore": 1.6, "vegetarian": 1.35, "vegan": 1.35, "pescatarian": 1.5},
                "carb_ratio": 0.62,
            },
        }
        strategy_profile = strategy_profiles.get(strategy)

        target_calories = tdee
        if strategy_profile:
            target_calories = strategy_profile["calories"](tdee)
        elif goal == "lose_weight":
            target_calories = max(tdee - 500, tdee * 0.75)
        elif goal == "gain_muscle":
            target_calories = tdee + 300
        target_calories = round(target_calories, 0)

        if weight and weight > 0:
            protein_g_per_kg_map = {
                "lose_weight": {"omnivore": 2.0, "vegetarian": 1.4, "vegan": 1.4, "pescatarian": 1.8},
                "gain_muscle": {"omnivore": 1.8, "vegetarian": 1.6, "vegan": 1.6, "pescatarian": 1.7},
                "maintain": {"omnivore": 1.4, "vegetarian": 1.2, "vegan": 1.2, "pescatarian": 1.3},
            }
            g_per_kg = (
                (strategy_profile or {}).get("protein_g_per_kg", {}).get(diet_key)
                or protein_g_per_kg_map.get(goal, {}).get(diet_key, 1.6)
            )
            protein_g = round(weight * g_per_kg, 1)

            max_protein_pct = 0.32 if diet_key in ("vegetarian", "vegan") else 0.40
            max_protein_cal = target_calories * max_protein_pct
            if protein_g * 4 > max_protein_cal:
                protein_g = round(max_protein_cal / 4, 1)
        else:
            if strategy == "deficit_high_satiety":
                if diet_key in ("vegetarian", "vegan"):
                    p_percent, c_percent, f_percent = 0.30, 0.45, 0.25
                else:
                    p_percent, c_percent, f_percent = 0.40, 0.35, 0.25
            elif strategy == "deficit_balanced":
                if diet_key in ("vegetarian", "vegan"):
                    p_percent, c_percent, f_percent = 0.28, 0.47, 0.25
                else:
                    p_percent, c_percent, f_percent = 0.34, 0.41, 0.25
            elif strategy == "surplus_balanced":
                p_percent, c_percent, f_percent = 0.27, 0.50, 0.23
            elif strategy == "surplus_high_protein":
                p_percent, c_percent, f_percent = 0.30, 0.50, 0.20
            elif strategy == "maintenance_training_support":
                p_percent, c_percent, f_percent = 0.28, 0.47, 0.25
            elif strategy == "maintenance_health_support":
                p_percent, c_percent, f_percent = 0.27, 0.43, 0.30
            elif goal == "lose_weight":
                if diet_key in ("vegetarian", "vegan"):
                    p_percent, c_percent, f_percent = 0.30, 0.45, 0.25
                else:
                    p_percent, c_percent, f_percent = 0.40, 0.35, 0.25
            elif goal == "gain_muscle":
                p_percent, c_percent, f_percent = 0.30, 0.50, 0.20
            else:
                p_percent, c_percent, f_percent = 0.30, 0.45, 0.25
            protein_g = round((target_calories * p_percent) / 4, 1)

        protein_cal = protein_g * 4
        remaining_cal = target_calories - protein_cal

        if strategy_profile:
            carb_ratio_of_remaining = strategy_profile["carb_ratio"]
        elif goal == "lose_weight":
            carb_ratio_of_remaining = 0.55
        elif goal == "gain_muscle":
            carb_ratio_of_remaining = 0.65
        else:
            carb_ratio_of_remaining = 0.60

        carbs_g = round((remaining_cal * carb_ratio_of_remaining) / 4, 1)
        fat_g = round((remaining_cal * (1 - carb_ratio_of_remaining)) / 9, 1)

        return {
            "calories": target_calories,
            "protein": protein_g,
            "carbs": carbs_g,
            "fat": fat_g,
        }

    @staticmethod
    def optimize_meal(
        available_foods: List[Dict],
        target_macros: Dict[str, float],
        max_grams: float = 400.0,
    ) -> List[Dict]:
        """
        Sử dụng least squares để tìm lượng gram cho từng món sao cho bám sát
        mục tiêu calo và macro của bữa ăn.
        """
        num_foods = len(available_foods)
        if num_foods == 0:
            return []

        def error_func(x):
            calc_calories = sum(x[i] * (available_foods[i].get("calories", 0)) for i in range(num_foods))
            calc_protein = sum(x[i] * (available_foods[i].get("protein", 0)) for i in range(num_foods))
            calc_carbs = sum(x[i] * (available_foods[i].get("carbs", 0)) for i in range(num_foods))
            calc_fat = sum(x[i] * (available_foods[i].get("fat", 0)) for i in range(num_foods))

            cal_err = (calc_calories - target_macros["calories"]) / target_macros["calories"]
            pro_err = (calc_protein - target_macros["protein"]) / target_macros["protein"]
            carb_err = (calc_carbs - target_macros["carbs"]) / target_macros["carbs"] if target_macros["carbs"] > 0 else 0
            fat_err = (calc_fat - target_macros["fat"]) / target_macros["fat"] if target_macros["fat"] > 0 else 0
            return np.array([cal_err, pro_err, carb_err, fat_err]) * 10

        x0 = np.ones(num_foods)
        upper_bound = max(max_grams / 100.0, 0.5)
        bounds = (np.array([0.3] * num_foods), np.array([upper_bound] * num_foods))
        res = opt.least_squares(error_func, x0, bounds=bounds)

        result_foods = []
        for i, qty in enumerate(res.x):
            grams = round(qty * 100)
            if grams >= 30:
                item = available_foods[i].copy()
                item["calculated_grams"] = grams
                item["calculated_calories"] = round(qty * item.get("calories", 0), 1)
                item["calculated_protein"] = round(qty * item.get("protein", 0), 1)
                item["calculated_carbs"] = round(qty * item.get("carbs", 0), 1)
                item["calculated_fat"] = round(qty * item.get("fat", 0), 1)
                result_foods.append(item)

        return result_foods
