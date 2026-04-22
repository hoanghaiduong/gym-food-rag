# NutritionIntentService - Phan tich y dinh dinh duong

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/nutrition_intent_service.py` (~800 dong)
> **Class chinh:** `NutritionIntentService`
> **Version:** `intent_parser_v2`

---

## 1. Tong quan

`NutritionIntentService` phan tich y dinh dinh duong cua nguoi dung tu:
- Profile da luu (goal, dietary preference, allergies)
- Request hien tai (instruction text, must_include, excluded_foods)

No su dung **2 che do phan tich** ket hop: rule-based (heuristic) va LLM-based
(semantic parser), roi merge ket qua thanh mot `NutritionIntent` thong nhat.

```
User Profile + Request
        |
        v
+-------------------+     +--------------------+
| _build_default_   |     | _build_heuristic_  |
|  intent()         |     |  intent()          |
| (tu profile)      |     | (regex + keywords) |
+-------------------+     +--------------------+
        |                          |
        v                          v
   default_intent          heuristic_intent
        |                          |
        +----------+---------------+
                   |
            _merge_intents()
                   |
                   v
            merged_intent
                   |
                   v
        +--------------------+
        | LLM Semantic       |
        | Parser (Ollama)    |
        +--------------------+
                   |
                   v
            llm_intent
                   |
                   v
            _merge_intents(merged, llm)
                   |
                   v
         Final NutritionIntent
```

---

## 2. NutritionIntent Schema Output

`NutritionIntent` la Pydantic model chua tat ca y dinh da phan tich:

```python
class NutritionIntent:
    goal: str | None                    # "gain_muscle"|"lose_weight"|"maintain"
    priorities: list[str]               # ["protein","satiety","recovery",...]
    hard_constraints: HardConstraints
    soft_preferences: SoftPreferences
    meal_preferences: MealPreferences
    notes: list[str]
    confidence: float                   # 0.0 - 1.0
    source: str                         # "profile_request_defaults"|"heuristic_parser"|...
    dietary_override: bool              # True neu must_include conflict voi dietary
```

### 2.1 HardConstraints
```python
class HardConstraints:
    dietary_preference: str | None    # "omnivore"|"vegetarian"|"vegan"|"pescatarian"
    allergies: list[str]              # ["dairy","egg","soy",...]
    must_avoid: list[str]             # ["do chien","nuoc ngot",...]
```

### 2.2 SoftPreferences
```python
class SoftPreferences:
    must_include: list[str]           # ["uc ga","trung",...]
    preferred_foods: list[str]        # ["ca hoi","khoai lang",...]
    disliked_foods: list[str]         # ["gan","long",...]
    cooking_complexity: str | None    # "easy"|"medium"|"any"
    budget_level: str | None          # "low"|"medium"|"high"
    meal_style: str | None            # "simple"|"traditional"|"high_protein"|"light"|"balanced"
```

### 2.3 MealPreferences
```python
class MealPreferences:
    meal_count: int | None            # 3-5
    pre_workout_meal: bool
    post_workout_meal: bool
    late_dinner: bool
    satiety_preference: str | None    # "high"|"normal"|"light"
```

---

## 3. Alias Maps - Tu dien chuyen doi tieng Viet

### 3.1 GOAL_ALIASES
```
"tang_co"        -> "gain_muscle"
"tang_can_sach"  -> "gain_muscle"
"giam_can"       -> "lose_weight"
"giam_mo"        -> "lose_weight"
"siet_can"       -> "lose_weight"
"giu_can"        -> "maintain"
"can_bang"        -> "maintain"
```

### 3.2 DIETARY_ALIASES
```
"an_tap"      -> "omnivore"
"an_chay"     -> "vegetarian"
"thuan_chay"  -> "vegan"
"an_ca"       -> "pescatarian"
```

### 3.3 ALLERGY_ALIASES
```
"sua"       -> "dairy"     "trung"    -> "egg"
"dau_nanh"  -> "soy"       "dau_phong"-> "peanut"
"hat_dieu"  -> "tree_nut"  "lua_mi"   -> "gluten"
"tom"/"cua" -> "shellfish" "ca"       -> "fish"
"me"        -> "sesame"
```

### 3.4 PRIORITY_ALIASES
```
"dam"        -> "protein"    "no_lau"     -> "satiety"
"phuc_hoi"   -> "recovery"   "de_nau"     -> "simplicity"
"ngan_sach"  -> "budget"     "da_dang"    -> "variety"
"thanh_dam"  -> "lightness"  "vitamin"    -> "micronutrients"
"de_tieu"    -> "digestion"
```

### 3.5 COOKING_COMPLEXITY_ALIASES / BUDGET_LEVEL_ALIASES / MEAL_STYLE_ALIASES
```
"de_nau"/"nhanh"  -> "easy"      "re"/"tiet_kiem" -> "low"
"vua"             -> "medium"    "cao_cap"        -> "high"
"don_gian"        -> "simple"    "truyen_thong"   -> "traditional"
"thanh_dam"       -> "light"     "can_bang"       -> "balanced"
```

---

## 4. Che do phan tich chi tiet

### 4.1 Default Intent (tu profile)
`_build_default_intent(profile, request)`:

- Lay goal, dietary, allergies tu profile da luu
- Thiet lap priorities mac dinh theo goal:
  - `gain_muscle`: ["protein", "recovery"]
  - `lose_weight`: ["protein", "satiety", "lightness"]
  - `maintain`: ["variety", "micronutrients"]
- Confidence: 0.55
- Source: "profile_request_defaults"

### 4.2 Heuristic Intent (regex + keyword matching)
`_build_heuristic_intent(profile, request)`:

Phan tich `request.instruction` bang keyword matching:

**GOAL_HINTS** - Nhan dien muc tieu:
```python
GOAL_HINTS = {
    "gain_muscle": ["tang co", "bulk", "bulking", "muscle gain",
                    "phuc hoi sau tap", "post workout", "sau tap"],
    "lose_weight": ["giam can", "giam mo", "fat loss", "cutting",
                    "it dau mo", "thanh dam"],
    "maintain":    ["giu can", "can bang", "maintain"],
}
```

**PRIORITY_HINTS** - Nhan dien uu tien:
```python
PRIORITY_HINTS = {
    "protein": ["protein", "dam", "giau dam", "high protein"],
    "satiety": ["no lau", "khong doi", "no bung"],
    "recovery": ["sau tap", "post workout", "phuc hoi"],
    "simplicity": ["de nau", "de lam", "nhanh", "don gian"],
    "budget": ["ngan sach", "gia re", "tiet kiem"],
    "variety": ["da dang", "doi mon", "nhieu lua chon"],
    "lightness": ["thanh dam", "it dau mo", "nhe bung"],
    "micronutrients": ["vitamin", "khoang chat", "vi chat"],
    "digestion": ["de tieu", "nhe bung"],
}
```

**Nhan dien thuc pham** - `_detect_food_mentions`:
- Tim cac trigger words: "tranh", "khong an", "phai co", "uu tien", "thich", ...
- Tach phan sau trigger bang regex: `,`, `va`, `voi`, `hoac`, `/`
- Loc bo tu khoa ky thuat: "bua", "calo", "macro", "gram"
- Gioi han 3 mon/trigger, 8 mon/list

**Auto-enrich priorities**:
- `post_workout_meal=True` -> them "recovery", "protein"
- `satiety_preference="high"` -> them "satiety"
- `cooking_complexity="easy"` -> them "simplicity"
- `budget_level="low"` -> them "budget"

Confidence: 0.45 (neu co instruction), 0.0 (neu khong)

### 4.3 LLM Semantic Parser
`parse_intent()` goi LLM khi co instruction:

1. Build prompt voi 2 vi du (Example A, B)
2. Gui den Ollama voi temperature=0.0
3. Parse JSON response
4. Normalize payload qua `_normalize_payload()`
5. Merge voi merged_intent

LLM prompt bao gom:
- Allowed values cho moi field
- Quy tac xu ly ("avoid" -> must_avoid, khong phai allergies)
- Stored profile + current request + base intent draft
- JSON schema mau

**Fallback**: Neu LLM fail -> dung heuristic intent + source="heuristic_fallback"

---

## 5. apply_to_profile() va apply_to_request()

### 5.1 `apply_to_profile(profile, intent) -> dict`
Ap dung intent len profile:

```python
effective_profile = deepcopy(profile)
# Goal override
effective_profile["target_goal"] = intent.goal
# Dietary preference override
effective_profile["dietary_preference"] = intent.hard_constraints.dietary_preference
# Dietary override flag (cho two-pass retrieval)
effective_profile["dietary_override"] = intent.dietary_override
# Merge allergy tags
effective_profile["allergy_tags"] = merge(profile.allergy_tags, intent.allergies)
```

### 5.2 `apply_to_request(request, intent) -> NutritionRecommendationRequest`
Ap dung intent len request:

```python
request.meal_count = intent.meal_preferences.meal_count or request.meal_count
request.must_include = merge(request.must_include, intent.must_include)
request.excluded_foods = merge(request.excluded_foods, intent.must_avoid + intent.disliked_foods)
```

---

## 6. Dietary Override Detection

`_detect_dietary_override(profile, request, intent) -> bool`

Phat hien conflict giua dietary preference va must_include:
- Chi kich hoat khi profile la "vegetarian" hoac "vegan"
- Kiem tra must_include co chua keyword thit/ca:
  `"ga", "thit", "beef", "chicken", "pork", "ca", "fish", "tom", ...`
- Neu co conflict -> return True
- Workflow se dung flag nay cho two-pass retrieval

---

## 7. Merge Logic

`_merge_intents(base, overlay)`:

| Field                    | Merge Strategy                        |
|--------------------------|---------------------------------------|
| goal                     | Overlay ghi de neu co                 |
| priorities               | Merge list, dedup                     |
| confidence               | Lay max                               |
| source                   | Lay overlay                           |
| dietary_preference       | Overlay ghi de neu co                 |
| allergies                | Merge list, dedup                     |
| must_avoid               | Merge list, dedup                     |
| must_include             | Merge list, dedup                     |
| preferred_foods          | Merge list, dedup                     |
| disliked_foods           | Merge list, dedup                     |
| cooking_complexity       | Overlay ghi de neu co                 |
| budget_level             | Overlay ghi de neu co                 |
| meal_style               | Overlay ghi de neu co                 |
| meal_count               | Overlay ghi de neu co                 |
| pre/post_workout_meal    | OR (giua base va overlay)             |
| late_dinner              | OR                                    |
| satiety_preference       | Overlay ghi de neu co                 |

`_merge_list(base, overlay, max_items=12)`:
- Merge 2 list, dedup bang ascii_normalize, giu thu tu
- Gioi han max_items de tranh list qua dai

---

## 8. Normalization

Moi field duoc normalize truoc khi luu:
- `_normalize_goal()`: Qua GOAL_ALIASES, default None
- `_normalize_dietary_preference()`: Qua DIETARY_ALIASES
- `_normalize_allergies()`: Split bang `,;/`, normalize tung tag
- `_normalize_priorities()`: Qua PRIORITY_ALIASES, max 6
- `_normalize_meal_count()`: Int trong [3, 5]
- `_normalize_confidence()`: Float trong [0.0, 1.0]
- `_clean_food_list()`: Strip + collapse spaces, max 8 items

---

## 9. Vi du su dung

```python
# Input
profile = {"target_goal": "maintain", "dietary_preference": "omnivore"}
request = NutritionRecommendationRequest(
    instruction="giam mo, no lau, de nau, tranh do chien va sua",
    meal_count=3,
)

# Output NutritionIntent
intent = NutritionIntent(
    goal="lose_weight",                        # tu GOAL_HINTS
    priorities=["satiety", "simplicity"],       # tu PRIORITY_HINTS
    hard_constraints={
        "dietary_preference": None,
        "allergies": [],
        "must_avoid": ["do chien", "sua"],      # tu trigger "tranh"
    },
    soft_preferences={
        "cooking_complexity": "easy",           # tu "de nau"
        "meal_style": None,
    },
    meal_preferences={
        "meal_count": 3,
        "satiety_preference": "high",           # tu "no lau"
    },
    confidence=0.86,
    source="llm_semantic_parser",
)
```

---

## 10. Singleton Instance

```python
nutrition_intent_service = NutritionIntentService()
```

Service duoc khoi tao 1 lan o module level va import truc tiep.

---

## 11. Lien ket tai lieu

- [NutritionWorkflowService](./nutrition-workflow.md) - Su dung intent service
- [CanonicalKnowledgeService](./canonical-knowledge.md) - Truy hoi thuc pham
- [NutritionService](./nutrition-optimizer.md) - Tinh TDEE va macro
- [BGEEmbeddingService](./embedding-service.md) - Tao embedding
