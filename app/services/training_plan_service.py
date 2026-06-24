from __future__ import annotations

import unicodedata
from typing import Any, Callable, Iterable

from app.schemas.training import (
    TrainingDayPlan,
    TrainingExercise,
    TrainingRecommendationRequest,
)


DEFAULT_WORKOUTS_PER_WEEK = 3
DEFAULT_SESSION_MINUTES = 45
MIN_SAFE_SESSION_MINUTES = 20
MAX_RECOMMENDED_FREQUENCY = 6

GOAL_ALIASES = {
    "gain_muscle": "gain_muscle",
    "tang_co": "gain_muscle",
    "tang_can": "gain_muscle",
    "lose_weight": "lose_weight",
    "lose_fat": "lose_weight",
    "fat_loss": "lose_weight",
    "giam_mo": "lose_weight",
    "giam_can": "lose_weight",
    "maintain": "maintain",
    "duy_tri": "maintain",
    "endurance": "endurance",
    "suc_ben": "endurance",
    "mobility": "mobility",
    "linh_hoat": "mobility",
}

GOAL_DEFAULT_TRAINING_TYPES = {
    "gain_muscle": ["gym", "calisthenics"],
    "lose_weight": ["gym", "cardio"],
    "maintain": ["gym", "cardio", "mobility"],
    "endurance": ["running", "cardio"],
    "mobility": ["mobility", "yoga"],
}

GOAL_FOCUS_CYCLE = {
    "gain_muscle": [
        ("Full-body strength", "Sức mạnh toàn thân"),
        ("Lower body + core", "Chân và core"),
        ("Upper body push/pull", "Thân trên đẩy/kéo"),
        ("Hypertrophy accessories", "Phụ trợ tăng cơ"),
        ("Conditioning recovery", "Điều hòa phục hồi"),
        ("Mobility reset", "Linh hoạt và phục hồi"),
    ],
    "lose_weight": [
        ("Full-body circuit", "Circuit toàn thân"),
        ("Zone 2 cardio", "Cardio nền"),
        ("Strength maintenance", "Giữ cơ"),
        ("Intervals", "Cardio ngắt quãng"),
        ("Core + mobility", "Core và linh hoạt"),
    ],
    "maintain": [
        ("Full-body strength", "Sức mạnh toàn thân"),
        ("Zone 2 cardio", "Cardio nền"),
        ("Upper/lower balance", "Cân bằng thân trên/thân dưới"),
        ("Mobility reset", "Linh hoạt và phục hồi"),
    ],
    "endurance": [
        ("Zone 2 cardio", "Cardio nền"),
        ("Tempo intervals", "Tempo/interval"),
        ("Strength support", "Sức mạnh hỗ trợ"),
        ("Long easy session", "Buổi dài nhẹ"),
    ],
    "mobility": [
        ("Mobility flow", "Chuỗi linh hoạt"),
        ("Core stability", "Ổn định core"),
        ("Low-impact conditioning", "Điều hòa ít tác động"),
    ],
}


class TrainingPlanService:
    def __init__(self, profile_builder: Callable[[dict[str, Any]], dict[str, Any]] | None = None):
        self._profile_builder = profile_builder

    def build_recommendation(
        self,
        current_user: dict[str, Any],
        request: TrainingRecommendationRequest,
    ) -> dict[str, Any]:
        profile = self._build_profile(current_user)
        goal = self._resolve_goal(request.goal or profile.get("goal_normalized_internal") or profile.get("target_goal"))
        weekly_frequency = self._resolve_weekly_frequency(request, profile)
        session_minutes = self._resolve_session_minutes(request, profile)
        training_types = self._resolve_training_types(request, profile, goal)
        equipment = _normalize_list(request.equipment)
        intensity = self._resolve_intensity(request.experience_level, goal, profile, request.limitations)
        limitations = self._collect_limitations(profile, request.limitations)

        schedule = [
            self._build_day_plan(
                day_index=index + 1,
                goal=goal,
                focus=self._focus_for_day(goal, index),
                session_minutes=session_minutes,
                intensity=intensity,
                training_types=training_types,
                equipment=equipment,
                experience_level=request.experience_level,
                limitations=limitations,
            )
            for index in range(weekly_frequency)
        ]

        issues = self._build_validation_issues(profile, request, limitations)
        return {
            "engine": {
                "decision_engine": "TrainingPlanService",
                "strategy": "deterministic_goal_profile_rules",
                "llm_used": "false",
            },
            "profile_summary": self._profile_summary(profile, request, training_types, equipment),
            "goal": goal,
            "weekly_frequency": weekly_frequency,
            "session_minutes": session_minutes,
            "intensity": intensity,
            "schedule": [day.model_dump() for day in schedule],
            "progression": self._progression(goal, request.experience_level),
            "safety_notes": self._safety_notes(limitations, request.experience_level),
            "nutrition_alignment": self._nutrition_alignment(goal, request.include_nutrition_timing),
            "validation": {
                "passed": not any(issue["severity"] == "error" for issue in issues),
                "issues": issues,
            },
        }

    def build_options(self) -> dict[str, Any]:
        return {
            "goals": [
                {"value": "gain_muscle", "label": "Tăng cơ", "backend_value": "gain_muscle"},
                {"value": "lose_weight", "label": "Giảm mỡ", "backend_value": "lose_weight"},
                {"value": "maintain", "label": "Duy trì", "backend_value": "maintain"},
                {"value": "endurance", "label": "Tăng sức bền", "backend_value": "endurance"},
                {"value": "mobility", "label": "Linh hoạt/phục hồi", "backend_value": "mobility"},
            ],
            "experience_levels": [
                {"value": "beginner", "label": "Mới bắt đầu", "backend_value": "beginner"},
                {"value": "intermediate", "label": "Trung cấp", "backend_value": "intermediate"},
                {"value": "advanced", "label": "Nâng cao", "backend_value": "advanced"},
            ],
            "training_types": [
                {"value": "gym", "label": "Gym", "backend_value": "gym"},
                {"value": "cardio", "label": "Cardio", "backend_value": "cardio"},
                {"value": "running", "label": "Chạy bộ", "backend_value": "running"},
                {"value": "calisthenics", "label": "Calisthenics", "backend_value": "calisthenics"},
                {"value": "yoga", "label": "Yoga", "backend_value": "yoga"},
                {"value": "mobility", "label": "Mobility", "backend_value": "mobility"},
            ],
            "equipment": [
                {"value": "bodyweight", "label": "Không dụng cụ", "backend_value": "bodyweight"},
                {"value": "dumbbell", "label": "Tạ đơn", "backend_value": "dumbbell"},
                {"value": "barbell", "label": "Thanh đòn", "backend_value": "barbell"},
                {"value": "machine", "label": "Máy tập", "backend_value": "machine"},
                {"value": "resistance_band", "label": "Dây kháng lực", "backend_value": "resistance_band"},
            ],
        }

    def _build_profile(self, current_user: dict[str, Any]) -> dict[str, Any]:
        if self._profile_builder:
            return self._profile_builder(current_user)
        from app.services.nutrition_workflow_service import nutrition_workflow_service

        return nutrition_workflow_service.build_profile(current_user)

    def _resolve_goal(self, raw_goal: Any) -> str:
        normalized = _normalize_text(raw_goal)
        return GOAL_ALIASES.get(normalized, GOAL_ALIASES.get(str(raw_goal or ""), "maintain"))

    def _resolve_weekly_frequency(
        self,
        request: TrainingRecommendationRequest,
        profile: dict[str, Any],
    ) -> int:
        raw = request.workouts_per_week or _safe_int(profile.get("workouts_per_week")) or DEFAULT_WORKOUTS_PER_WEEK
        return max(1, min(MAX_RECOMMENDED_FREQUENCY, int(raw)))

    def _resolve_session_minutes(
        self,
        request: TrainingRecommendationRequest,
        profile: dict[str, Any],
    ) -> int:
        raw = request.workout_minutes or _safe_int(profile.get("workout_minutes")) or DEFAULT_SESSION_MINUTES
        return max(MIN_SAFE_SESSION_MINUTES, int(raw))

    def _resolve_training_types(
        self,
        request: TrainingRecommendationRequest,
        profile: dict[str, Any],
        goal: str,
    ) -> list[str]:
        explicit_types = _normalize_list(request.training_types)
        if explicit_types:
            return explicit_types
        profile_types = _normalize_list(profile.get("training_types"))
        if profile_types:
            return profile_types
        return GOAL_DEFAULT_TRAINING_TYPES[goal]

    def _resolve_intensity(
        self,
        experience_level: str,
        goal: str,
        profile: dict[str, Any],
        limitations: list[str],
    ) -> str:
        if limitations or _normalize_list(profile.get("medical_conditions")):
            return "low"
        if experience_level == "advanced" and goal in {"gain_muscle", "endurance"}:
            return "high"
        if experience_level == "beginner":
            return "moderate"
        return "moderate"

    def _focus_for_day(self, goal: str, day_index: int) -> tuple[str, str]:
        cycle = GOAL_FOCUS_CYCLE[goal]
        return cycle[day_index % len(cycle)]

    def _build_day_plan(
        self,
        *,
        day_index: int,
        goal: str,
        focus: tuple[str, str],
        session_minutes: int,
        intensity: str,
        training_types: list[str],
        equipment: list[str],
        experience_level: str,
        limitations: list[str],
    ) -> TrainingDayPlan:
        focus_key, focus_label = focus
        exercises = self._exercise_template(
            goal=goal,
            focus_key=focus_key,
            intensity=intensity,
            training_types=training_types,
            equipment=equipment,
            experience_level=experience_level,
            limitations=limitations,
        )
        return TrainingDayPlan(
            day_index=day_index,
            title=f"Buổi {day_index}: {focus_label}",
            focus=focus_key,
            estimated_minutes=session_minutes,
            warmup=self._warmup(training_types, limitations),
            exercises=exercises,
            cooldown=["Thả lỏng 5 phút", "Giãn cơ nhóm chính đã tập", "Uống nước và theo dõi nhịp thở"],
            notes=self._day_notes(goal, limitations),
        )

    def _exercise_template(
        self,
        *,
        goal: str,
        focus_key: str,
        intensity: str,
        training_types: list[str],
        equipment: list[str],
        experience_level: str,
        limitations: list[str],
    ) -> list[TrainingExercise]:
        low_impact = bool(limitations) or "yoga" in training_types or "mobility" in training_types
        bodyweight_only = equipment == ["bodyweight"] or ("bodyweight" in equipment and "gym" not in training_types)
        strength_sets = 4 if experience_level == "advanced" and intensity == "high" else 3
        rest = 90 if intensity == "high" else 60

        if goal == "lose_weight" or "cardio" in training_types or "running" in training_types:
            return [
                TrainingExercise(name="Goblet squat hoặc bodyweight squat", category="strength", sets=3, reps="10-12", intensity=intensity, rest_seconds=rest),
                TrainingExercise(name="Incline push-up hoặc machine chest press", category="strength", sets=3, reps="8-12", intensity=intensity, rest_seconds=rest),
                TrainingExercise(name="Row với dây/tạ/máy", category="strength", sets=3, reps="10-12", intensity=intensity, rest_seconds=rest),
                TrainingExercise(name="Cardio nền" if low_impact else "Interval cardio", category="cardio", duration_minutes=20, intensity="low" if low_impact else "moderate", rest_seconds=30),
            ]

        if goal == "mobility":
            return [
                TrainingExercise(name="Hip hinge drill", category="mobility", sets=2, reps="8-10", intensity="low", rest_seconds=30),
                TrainingExercise(name="World greatest stretch", category="mobility", sets=2, reps="6 mỗi bên", intensity="low", rest_seconds=30),
                TrainingExercise(name="Dead bug hoặc bird dog", category="core", sets=3, reps="8-12", intensity="low", rest_seconds=45),
                TrainingExercise(name="Đi bộ nhẹ", category="cardio", duration_minutes=15, intensity="low", rest_seconds=30),
            ]

        if "Lower" in focus_key:
            main_lift = "Bodyweight squat" if bodyweight_only else "Squat pattern"
            accessory = "Hip hinge bridge" if bodyweight_only else "Romanian deadlift"
        elif "Upper" in focus_key:
            main_lift = "Push-up pattern" if bodyweight_only else "Bench/push-up pattern"
            accessory = "Band row hoặc towel row" if bodyweight_only else "Row/pull pattern"
        else:
            main_lift = "Bodyweight squat" if bodyweight_only else "Squat hoặc leg press"
            accessory = "Band row hoặc towel row" if bodyweight_only else "Dumbbell row hoặc cable row"

        return [
            TrainingExercise(name=main_lift, category="strength", sets=strength_sets, reps="6-10", intensity=intensity, rest_seconds=rest),
            TrainingExercise(name=accessory, category="strength", sets=strength_sets, reps="8-12", intensity=intensity, rest_seconds=rest),
            TrainingExercise(name="Overhead press hoặc incline press", category="strength", sets=3, reps="8-12", intensity=intensity, rest_seconds=rest),
            TrainingExercise(name="Plank hoặc carry", category="core", sets=3, reps="30-45 giây", intensity="moderate", rest_seconds=45),
        ]

    def _warmup(self, training_types: list[str], limitations: list[str]) -> list[str]:
        if limitations:
            return ["Đi bộ nhẹ 5 phút", "Khởi động khớp chậm", "Tập thử động tác với biên độ an toàn"]
        if "running" in training_types:
            return ["Đi bộ nhanh 5 phút", "Dynamic leg swing", "Chạy nhẹ 3 phút"]
        return ["Cardio nhẹ 5 phút", "Xoay khớp vai/hông/gối", "Tập 1 set khởi động cho động tác chính"]

    def _collect_limitations(self, profile: dict[str, Any], request_limitations: list[str]) -> list[str]:
        return [*_normalize_list(profile.get("medical_conditions")), *_normalize_list(request_limitations)]

    def _build_validation_issues(
        self,
        profile: dict[str, Any],
        request: TrainingRecommendationRequest,
        limitations: list[str],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if not profile.get("is_profile_completed"):
            issues.append({
                "code": "profile_incomplete",
                "severity": "warning",
                "message": "Hồ sơ chưa đầy đủ; kế hoạch dùng mặc định an toàn.",
            })
        if limitations:
            issues.append({
                "code": "medical_or_mobility_limitations_present",
                "severity": "warning",
                "message": "Có bệnh nền/hạn chế vận động; nên xác nhận với chuyên gia trước khi tăng cường độ.",
                "details": {"limitations": limitations},
            })
        if request.workouts_per_week and request.workouts_per_week > MAX_RECOMMENDED_FREQUENCY:
            issues.append({
                "code": "frequency_capped",
                "severity": "warning",
                "message": "Tần suất đã được giới hạn để có ngày phục hồi.",
            })
        return issues

    def _profile_summary(
        self,
        profile: dict[str, Any],
        request: TrainingRecommendationRequest,
        training_types: list[str],
        equipment: list[str],
    ) -> dict[str, Any]:
        return {
            "user_id": profile.get("user_id") or profile.get("id"),
            "goal_source": "request" if request.goal else "profile",
            "activity_level": profile.get("activity_level"),
            "training_types": training_types,
            "equipment": equipment,
            "experience_level": request.experience_level,
        }

    def _progression(self, goal: str, experience_level: str) -> list[str]:
        if experience_level == "beginner":
            return [
                "Giữ kỹ thuật ổn định trong 2 tuần đầu trước khi tăng tải.",
                "Mỗi tuần chỉ tăng 1 biến: thêm 1-2 reps hoặc tăng tạ nhẹ.",
                "Nếu đau nhói hoặc chóng mặt, dừng buổi tập và giảm cường độ.",
            ]
        if goal == "endurance":
            return [
                "Tăng tổng thời lượng cardio tối đa 10% mỗi tuần.",
                "Giữ ít nhất 1 ngày nhẹ để hồi phục.",
            ]
        return [
            "Khi hoàn thành đủ reps ở tất cả set, tăng tải 2-5% ở tuần sau.",
            "Deload 1 tuần sau mỗi 4-6 tuần nếu hiệu suất giảm.",
        ]

    def _safety_notes(self, limitations: list[str], experience_level: str) -> list[str]:
        notes = ["Kế hoạch mang tính hỗ trợ fitness, không thay thế tư vấn y khoa."]
        if limitations:
            notes.append("Ưu tiên bài ít tác động, tránh tập tới ngưỡng đau và hỏi chuyên gia nếu có bệnh nền.")
        if experience_level == "beginner":
            notes.append("Ưu tiên học kỹ thuật, không tập tới thất bại cơ trong các tuần đầu.")
        return notes

    def _nutrition_alignment(self, goal: str, include_timing: bool) -> list[str]:
        if not include_timing:
            return []
        base = ["Ăn đủ nước và không tập lúc quá đói nếu buổi tập trên 45 phút."]
        if goal == "gain_muscle":
            base.append("Sau tập ưu tiên bữa có protein nạc và tinh bột chín để hỗ trợ phục hồi.")
        elif goal == "lose_weight":
            base.append("Giữ protein cao, kiểm soát năng lượng, tránh bù calo quá mức sau cardio.")
        else:
            base.append("Giữ bữa trước/sau tập cân bằng protein, carb và rau phù hợp với nutrition plan.")
        return base

    def _day_notes(self, goal: str, limitations: list[str]) -> list[str]:
        notes = []
        if limitations:
            notes.append("Có thể thay bài bằng biến thể nhẹ hơn nếu khó chịu.")
        if goal == "gain_muscle":
            notes.append("Nghỉ đủ giữa set để giữ chất lượng reps.")
        return notes


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, Iterable):
        raw_items = list(value)
    else:
        raw_items = [value]
    return [item for item in (_normalize_text(raw) for raw in raw_items) if item]


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.replace("_", " ").replace("-", " ").split()).replace(" ", "_")


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


training_plan_service = TrainingPlanService()
