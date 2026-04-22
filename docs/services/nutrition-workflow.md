# NutritionWorkflowService - Bo dieu phoi chinh cua he thong

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/nutrition_workflow_service.py` (~1800+ dong)
> **Class chinh:** `NutritionWorkflowService`

---

## 1. Tong quan

`NutritionWorkflowService` la service trung tam dieu phoi toan bo luong xu ly (workflow)
cua he thong goi y dinh duong cho nguoi tap gym. No ket noi tat ca cac service con lai
thanh mot pipeline hoan chinh:

```
User Request
    |
    v
+-------------------+     +----------------------+     +----------------+
| build_profile()   | --> | parse_intent()       | --> | compute_targets|
| (Chuan hoa user)  |     | (NutritionIntent)    |     | (TDEE + Macro) |
+-------------------+     +----------------------+     +----------------+
                                                              |
                                                              v
+---------------------+     +------------------------+     +------------------+
| _explain_via_llm()  | <-- | _run_deterministic_    | <-- | _retrieve_       |
| (LLM giai thich)    |     |  flow()                |     |  candidates()    |
+---------------------+     +------------------------+     +------------------+
                                    |
                                    v
                          +-------------------+
                          | _validate_plan()  |
                          | (Kiem tra chat    |
                          |  luong)           |
                          +-------------------+
                                    |
                                    v
                            Response JSON
```

Pipeline chinh theo thu tu:
1. **Profile** - Chuan hoa thong tin nguoi dung (tuoi, gioi tinh, can nang, v.v.)
2. **Intent** - Phan tich y dinh tu instruction (goal, dietary preference, allergies)
3. **TDEE** - Tinh TDEE va chia macro theo muc tieu
4. **Retrieve** - Truy hoi thuc pham tu Qdrant + local JSONL
5. **Optimize** - Toi uu pool ung vien theo vai tro dinh duong
6. **Plan** - Xay dung thuc don bang rule-based + SciPy optimizer
7. **Validate** - Kiem tra calo, macro, di ung, dietary preference
8. **Explain** - Giai thich thuc don bang LLM (hau ky, khong thay doi so lieu)

---

## 2. Khoi tao va Dependencies

```python
class NutritionWorkflowService:
    def __init__(self):
        self.knowledge = canonical_knowledge_service    # CanonicalKnowledgeService
        self.intent_parser = nutrition_intent_service    # NutritionIntentService
        self.llm = ollama_nutrition_service              # OllamaNutritionService
        self.state_store = redis_state_service           # RedisStateService
```

| Dependency                  | Vai tro                                      |
|-----------------------------|----------------------------------------------|
| `canonical_knowledge_service` | Truy hoi thuc pham tu Qdrant + local index |
| `nutrition_intent_service`    | Phan tich y dinh nguoi dung                |
| `NutritionService` (static)  | Tinh TDEE, macro, toi uu SciPy             |
| `ollama_nutrition_service`    | Goi LLM de giai thich thuc don             |
| `redis_state_service`         | Cache ket qua + luu workflow state         |

---

## 3. Cac Data Structure quan trong

### 3.1 GOAL_MAP
Chuyen doi cac gia tri goal dau vao (tieng Viet + tieng Anh) sang dang chuan:
```
"lose_weight", "cutting", "fat_loss", "giam_can", "giam_mo" --> "lose_weight"
"gain_muscle", "bulking", "gain", "tang_co"                 --> "gain_muscle"
"maintain", "maintenance", "giu_can"                         --> "maintain"
```

### 3.2 GENDER_MAP / ACTIVITY_MAP / DIETARY_MAP / ALLERGY_MAP
Tuong tu GOAL_MAP, chuyen doi cac gia tri tieng Viet sang dang chuan hoa:
- GENDER_MAP: `"nam"` -> `"male"`, `"nu"` -> `"female"`
- ACTIVITY_MAP: `"it_van_dong"` -> `"sedentary"`, `"nhe"` -> `"light"`, ...
- DIETARY_MAP: `"an_chay"` -> `"vegetarian"`, `"thuan_chay"` -> `"vegan"`, ...
- ALLERGY_MAP: `"sua"` -> `"dairy"`, `"trung"` -> `"egg"`, `"tom"` -> `"shellfish"`, ...

### 3.3 MEAL_TEMPLATES
Phan bo ti le calo cho tung bua theo so bua:
```python
MEAL_TEMPLATES = {
    3: [("Breakfast", 0.28), ("Lunch", 0.37), ("Dinner", 0.35)],
    4: [("Breakfast", 0.25), ("Lunch", 0.30), ("Dinner", 0.30), ("Snack", 0.15)],
    5: [("Breakfast", 0.22), ("Morning Snack", 0.10), ("Lunch", 0.28),
        ("Dinner", 0.28), ("Evening Snack", 0.12)],
}
```

### 3.4 GOAL_RETRIEVAL_GUIDES
Huong dan truy hoi theo muc tieu, dung de tao query cho Qdrant:
- `lose_weight`: "lean protein high fiber moderate carb whole foods for fat loss"
- `gain_muscle`: "high protein high energy complex carbohydrate foods for muscle gain"
- `maintain`: "balanced whole foods with protein carbs healthy fats micronutrients"

Moi guide co 3 phien ban: `en`, `vi`, `macro_focus`.

### 3.5 GOAL_POOL_RULES
Quy dinh so luong anchor cho tung vai tro theo muc tieu:
```python
GOAL_POOL_RULES = {
    "gain_muscle": {
        "pool_limit": 12,
        "protein_anchor_count": 4,
        "carb_anchor_count": 4,
        "healthy_fat_anchor_count": 0,
        "produce_anchor_count": 2,
        "balanced_anchor_count": 2,
    },
    "lose_weight": { ... protein: 3, carb: 2, fat: 2, produce: 3, balanced: 2 },
    "maintain":    { ... protein: 3, carb: 3, fat: 1, produce: 3, balanced: 2 },
}
```

### 3.6 REALISM_HARD_BLOCK / REALISM_DISCOURAGED
Bo loc thuc te de loai bo thuc pham khong phu hop lam mon chinh:
- **HARD_BLOCK name keywords**: `"toi "`, `"hanh "`, `"ot "`, `"nuoc mam"`, `"gia vi"`, `"keo"`, ...
- **HARD_BLOCK group keywords**: `"gia vi"`, `"nuoc cham"`, `"dau, mo, bo"`
- **DISCOURAGED name keywords**: `"long "`, `"tim "`, `"gan "`, `"ruoc"`, ...

---

## 4. Cac method chinh

### 4.1 `run_main_flow(current_user, request) -> dict`
Day la entry point chinh cua he thong. Luong xu ly:

1. Goi `build_profile()` de chuan hoa thong tin user
2. Kiem tra Redis cache (neu `request.use_cache = True`)
3. Goi `intent_parser.parse_intent()` de phan tich y dinh
4. Goi `intent_parser.apply_to_profile()` va `apply_to_request()`
5. Goi `_compute_targets()` de tinh TDEE + macro
6. Goi `_retrieve_candidates()` de truy hoi thuc pham
7. Goi `_run_deterministic_flow()` de tao thuc don
8. Goi `_compose_response()` de dong goi ket qua
9. Luu cache + workflow state vao Redis

Tra ve dict chua: `request_id`, `plan`, `validation`, `workflow_trace`, ...

### 4.2 `build_profile(current_user) -> dict`
Chuan hoa profile nguoi dung:
- Goi `_normalize_gender()`, `_normalize_activity_level()`,
  `_normalize_dietary_preference()`, `_normalize_goal()`, `_normalize_allergies()`
- Tra ve dict voi cac truong da chuan hoa

### 4.3 `normalize_profile_update(update_data) -> dict`
Chuan hoa du lieu cap nhat profile (dung cho API PUT/PATCH).

### 4.4 `_run_deterministic_flow(profile, request, targets, candidates, intent)`
Luong tao thuc don chinh (KHONG dung LLM de generate):

1. Goi `_build_rule_based_attempt()` de tao thuc don bang luat
2. Goi `_attach_plan_explanations()` de them giai thich (co the dung LLM)
3. Tinh `candidate_diagnostics` de debug

### 4.5 `_build_rule_based_attempt(profile, request, targets, candidates, intent)`
Tao thuc don bang 2 chien luoc song song:

1. **rule_based_mealwise** - Toi uu tung bua rieng le:
   - Chon subset candidates cho tung bua (`_build_meal_candidate_subset`)
   - Goi `NutritionService.optimize_meal()` voi macro target cua bua do
2. **rule_based_daily** - Toi uu ca ngay roi phan bo:
   - Chon subset cho ca ngay (`_build_daily_optimization_subset`)
   - Goi `optimize_meal()` voi macro target ca ngay
   - Phan bo ket qua vao cac bua theo remaining calories

Chon attempt tot nhat tu 2 chien luoc bang `_pick_best_attempt()`.

### 4.6 `_explain_via_llm()` (trong `_attach_plan_explanations`)
Dung LLM chi de GIAI THICH thuc don da tao, KHONG thay doi so lieu:
- Gui prompt gom profile, targets, validation, plan da tao
- LLM tra ve summary, reasoning, meal_explanations
- Merge vao plan da co bang `_merge_explanation_json()`
- Neu LLM fail -> dung default explanations tu `_build_default_summary()`

### 4.7 `_optimize_candidate_pool(profile, request, targets, candidates, intent)`
Toi uu va can bang pool ung vien truoc khi dua vao rule-based planner:

1. Goi `_supplement_candidates_from_local()` de bo sung tu local JSONL
2. Goi `_filter_candidates_for_meal_planning()` de loai hard_block
3. Chia candidates vao cac bucket: protein, carb, produce, balanced, healthy_fat
4. Dien theo thu tu uu tien tu GOAL_POOL_RULES
5. Gioi han bang `pool_limit`

### 4.8 `_goal_fit_score(candidate, goal, must_include, intent) -> float`
Tinh diem phu hop cua ung vien theo muc tieu. Cong thuc khac nhau cho tung goal:

**gain_muscle:**
```
score = 0.45 * protein_ratio + 0.30 * carb_ratio + 0.20 * energy_ratio
        + 0.08 * fiber + bonus_tags
```

**lose_weight:**
```
score = 0.45 * protein_density + 0.20 * protein_ratio + 0.22 * fiber_ratio
        + bonus_tags + healthy_fat_bonus
```

**maintain:**
```
score = 0.35 * protein + 0.25 * carbs + 0.15 * fat + 0.15 * produce + 0.10 * energy
```

Ket qua cuoi cung:
```
final = 0.55 * score + 0.20 * retrieval + 0.15 * quality + 0.22 * planner_weight
        + must_include_bonus + practicality_bonus + intent_alignment
        - produce_penalty - empty_density_penalty - practicality_penalty
```

### 4.9 `_intent_alignment_score(candidate, goal, intent) -> float`
Diem alignment voi y dinh nguoi dung. Xet cac yeu to:
- preferred_foods match: +0.45
- disliked_foods match: -0.9
- Priority "protein" + protein >= 18g: +0.20
- Priority "satiety" + protein >= 12 or fiber >= 4: +0.18
- Priority "recovery" + protein >= 15 + carbs >= 20: +0.22
- cooking_complexity "easy" + common food: +0.10
- budget_level "low" + affordable food: +0.10
- meal_style "high_protein" + protein >= 18: +0.15
- post_workout_meal + high protein + carbs: +0.14

### 4.10 `_candidate_realism_profile(candidate, goal) -> dict`
Danh gia tinh thuc te cua ung vien:
- **hard_block**: gia vi, nuoc cham, nguyen lieu kho, do ngot (cho lose_weight)
- **discouraged**: noi tang, hai san dac biet, fat cao
- **preferred**: protein tot, carb tot, rau xanh, phu hop goal

Tra ve dict chua: `hard_block`, `hard_block_reasons`, `discouraged_reasons`,
`preferred_reasons`, `normalized_name`, macro values, ...

---

## 5. Baselines (dung cho so sanh, danh gia)

### 5.1 `run_pure_generation_baseline(profile, request, targets)`
Baseline khong dung retrieval:
- Chi dung LLM generate toan bo thuc don tu kien thuc chung
- Khong co candidate list
- Dung de so sanh chat luong voi he thong RAG chinh

### 5.2 `run_rule_based_baseline(profile, request, targets, candidates)`
Baseline chi dung luat:
- Dung `_build_rule_based_attempt()` khong co LLM explanation
- Dung de so sanh voi pipeline day du

---

## 6. Validation (`_validate_plan`)

Kiem tra thuc don sau khi tao, gom cac checks:

| Check                        | Severity | Mo ta                                              |
|------------------------------|----------|----------------------------------------------------|
| `meal_count_mismatch`        | error    | So bua khong dung                                  |
| `unresolved_foods`           | error    | Mon khong tim thay trong knowledge base             |
| `grams_out_of_range`         | error    | Gram ngoai 30-400                                  |
| `allergy_violation`          | error    | Mon chua allergen cua user                         |
| `dietary_preference_violation`| error   | Mon khong phu hop dietary (tru dietary_override)   |
| `excluded_food_present`      | error    | Mon bi exclude van xuat hien                       |
| `must_include_missing`       | warning  | Mon yeu cau khong co trong thuc don                |
| `calorie_target_miss`        | error    | Calo lech > tolerance                              |
| `protein/carbs/fat_target_miss` | error | Macro lech > tolerance                            |
| `meal_realism_blocked_items` | error    | Mon bi hard_block van xuat hien                    |
| `meal_realism_role_coverage` | error    | Thieu protein/carb/produce anchors                 |

Ket qua tra ve: `passed`, `totals`, `calorie_error_pct`, `macro_deviation_pct`, `issues`

---

## 7. Vi du luong xu ly (Flow Trace)

```
Request: { user_id: "u123", meal_count: 3, goal: "gain_muscle",
           must_include: ["uc ga"], instruction: "sau tap, giau dam" }

1. build_profile()
   -> { age: 25, gender: "male", weight: 75, height: 175,
        activity_level: "active", target_goal: "gain_muscle" }

2. parse_intent()
   -> NutritionIntent(goal="gain_muscle", priorities=["protein","recovery"],
        post_workout_meal=True)

3. _compute_targets()
   -> { tdee: 2850, daily_calories: 3150, protein_g: 236,
        carbs_g: 394, fat_g: 70 }

4. _retrieve_candidates() [multi-query hybrid search + local supplement]
   -> 12 candidates: [Uc ga, Com gao lut, Khoai lang, Trung ga, ...]

5. _optimize_candidate_pool()
   -> Protein anchors: [Uc ga, Trung ga, Ca hoi]
      Carb anchors: [Com gao lut, Khoai lang, Yen mach]
      Produce: [Rau cai xanh, Sup lo]

6. _run_deterministic_flow() -> _build_rule_based_attempt()
   -> 2 strategies: mealwise + daily -> chon tot nhat

7. _validate_plan()
   -> { passed: true, calorie_error_pct: 4.2, macro_deviation_pct: 5.1 }

8. _attach_plan_explanations() (LLM explain)
   -> summary: "Thuc don 3 bua tap trung tang co voi 3150 kcal..."

9. Response JSON tra ve cho API
```

---

## 8. Two-Pass Retrieval (dietary_override)

Khi nguoi dung co dietary_preference la vegetarian nhung must_include mon thit:
1. **Pass 1**: Truy hoi must_include foods KHONG ap dung dietary filter
2. **Pass 2**: Truy hoi binh thuong voi dietary filter
3. Merge 2 tap ket qua, giu score cao hon
4. Validation bo qua `dietary_preference_violation` khi `dietary_override=True`

---

## 9. Lien ket tai lieu

- [CanonicalKnowledgeService](./canonical-knowledge.md) - Truy hoi thuc pham
- [NutritionService](./nutrition-optimizer.md) - Tinh TDEE va toi uu macro
- [NutritionIntentService](./intent-service.md) - Phan tich y dinh
- [BGEEmbeddingService](./embedding-service.md) - Tao embedding cho truy hoi
