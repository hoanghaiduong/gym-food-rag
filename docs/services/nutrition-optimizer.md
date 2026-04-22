# NutritionService - Tinh TDEE va Toi uu Macro bang SciPy

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/nutrition_service.py` (~119 dong)
> **Class chinh:** `NutritionService`

---

## 1. Tong quan

`NutritionService` cung cap 3 chuc nang cot loi cua he thong dinh duong:

1. **Tinh TDEE** - Total Daily Energy Expenditure bang cong thuc Mifflin-St Jeor
2. **Phan bo Macro** - Chia protein/carbs/fat theo muc tieu tap luyen
3. **Toi uu bua an** - Dung SciPy `least_squares` de tim luong gram toi uu

```
User Profile                     Muc tieu
(tuoi, gioi tinh, can nang,  --> TDEE --> Macro Targets --> SciPy Optimizer
 chieu cao, muc van dong)                                       |
                                                                v
                                                      Optimized Meal Plan
                                                      (gram cho tung mon)
```

Tat ca cac method deu la `@staticmethod` - khong can khoi tao instance.

---

## 2. calculate_tdee() - Tinh TDEE

### 2.1 Cong thuc Mifflin-St Jeor

Day la cong thuc duoc coi la chinh xac nhat hien nay cho tinh BMR:

```
Nam (male):
    BMR = (10 x can_nang_kg) + (6.25 x chieu_cao_cm) - (5 x tuoi) + 5

Nu (female):
    BMR = (10 x can_nang_kg) + (6.25 x chieu_cao_cm) - (5 x tuoi) - 161
```

### 2.2 He so van dong (Activity Multipliers)

```
TDEE = BMR x Activity Multiplier
```

| Activity Level | He so  | Mo ta tieng Viet                         |
|----------------|--------|------------------------------------------|
| `sedentary`    | 1.200  | It van dong (ngoi van phong)             |
| `light`        | 1.375  | Van dong nhe (tap 1-3 ngay/tuan)         |
| `moderate`     | 1.550  | Van dong vua (tap 3-5 ngay/tuan)         |
| `active`       | 1.725  | Van dong nhieu (tap 6-7 ngay/tuan)       |
| `very_active`  | 1.900  | Van dong qua muc (VDV, tap 2 lan/ngay)  |

**Mac dinh**: Neu activity_level khong hop le, dung `sedentary` (1.2).

### 2.3 Signature

```python
@staticmethod
def calculate_tdee(
    age: int,
    gender: str,       # "male" hoac "female"
    weight: float,     # kg
    height: float,     # cm
    activity_level: str # "sedentary"|"light"|"moderate"|"active"|"very_active"
) -> float
```

### 2.4 Vi du

```python
# Nam, 25 tuoi, 75kg, 175cm, tap 6 ngay/tuan
tdee = NutritionService.calculate_tdee(25, "male", 75, 175, "active")
# BMR = (10*75) + (6.25*175) - (5*25) + 5 = 750 + 1093.75 - 125 + 5 = 1723.75
# TDEE = 1723.75 * 1.725 = 2973.47 kcal

# Nu, 30 tuoi, 55kg, 160cm, tap 3-5 ngay/tuan
tdee = NutritionService.calculate_tdee(30, "female", 55, 160, "moderate")
# BMR = (10*55) + (6.25*160) - (5*30) - 161 = 550 + 1000 - 150 - 161 = 1239
# TDEE = 1239 * 1.55 = 1920.45 kcal
```

---

## 3. get_macro_targets() - Phan bo Macro

### 3.1 Dieu chinh Calo theo Goal

```
lose_weight:  target_calories = TDEE - 500  (thieu hut 500 kcal)
gain_muscle:  target_calories = TDEE + 300  (du thua 300 kcal)
maintain:     target_calories = TDEE        (giu nguyen)
```

### 3.2 Ti le Macro theo Goal

| Goal          | Protein | Carbs | Fat  | Ghi chu                           |
|---------------|---------|-------|------|-----------------------------------|
| `lose_weight` | 40%     | 30%   | 30%  | Tang protein giu co, giam carb    |
| `gain_muscle` | 30%     | 50%   | 20%  | Tang carb cho nang luong tap      |
| `maintain`    | 30%     | 45%   | 25%  | Can bang cho duy tri              |

### 3.3 Chuyen doi sang gram

```
Protein (g) = (target_calories * protein_pct) / 4    # 1g protein = 4 kcal
Carbs (g)   = (target_calories * carbs_pct) / 4      # 1g carbs = 4 kcal
Fat (g)     = (target_calories * fat_pct) / 9         # 1g fat = 9 kcal
```

### 3.4 Signature

```python
@staticmethod
def get_macro_targets(
    tdee: float,
    goal: str    # "lose_weight"|"gain_muscle"|"maintain"
) -> Dict[str, float]
```

Tra ve:
```python
{
    "calories": 2500.0,
    "protein": 187.5,   # gram
    "carbs": 281.3,      # gram
    "fat": 69.4          # gram
}
```

### 3.5 Vi du

```python
# TDEE = 2973 kcal, goal = gain_muscle
macros = NutritionService.get_macro_targets(2973, "gain_muscle")
# target_calories = 2973 + 300 = 3273
# protein = (3273 * 0.30) / 4 = 245.5g
# carbs   = (3273 * 0.50) / 4 = 409.1g
# fat     = (3273 * 0.20) / 9 = 72.7g
```

---

## 4. optimize_meal() - Toi uu bua an bang SciPy

### 4.1 Bai toan toi uu

Cho mot danh sach thuc pham voi thong tin dinh duong (tren 100g),
tim khoi luong (gram) cua tung mon sao cho tong macro gan nhat
voi target.

```
Minimize:  ||error(x)||^2

Trong do:
  x[i] = so don vi 100g cua mon thu i (vi du: 1.5 = 150g)

  error = [
    (tong_calories(x) - target_calories) / target_calories,
    (tong_protein(x)  - target_protein)  / target_protein,
    (tong_carbs(x)    - target_carbs)    / target_carbs,
    (tong_fat(x)      - target_fat)      / target_fat,
  ] * 10  (weight factor)
```

### 4.2 SciPy least_squares

```python
scipy.optimize.least_squares(
    fun=error_func,      # Ham tinh sai so
    x0=np.ones(n),       # Diem khoi tao: moi mon 100g
    bounds=(
        [0.3] * n,       # Toi thieu: 30g moi mon
        [4.0] * n        # Toi da: 400g moi mon
    )
)
```

**Tai sao dung `least_squares` thay vi `linprog`?**
- `linprog` yeu cau equality constraints chinh xac
- Dinh duong thuc te khong the chinh xac 100%
- `least_squares` toi thieu hoa tong sai so binh phuong
- Linh hoat hon, cho phep trade-off giua cac macro

### 4.3 Error Function chi tiet

```python
def error_func(x):
    # Tinh tong thuc te cua moi macro
    calc_calories = sum(x[i] * food[i]["calories"] for i in range(n))
    calc_protein  = sum(x[i] * food[i]["protein"]  for i in range(n))
    calc_carbs    = sum(x[i] * food[i]["carbs"]    for i in range(n))
    calc_fat      = sum(x[i] * food[i]["fat"]      for i in range(n))

    # Tinh sai so tuong doi (normalized)
    cal_err = (calc_calories - target["calories"]) / target["calories"]
    pro_err = (calc_protein  - target["protein"])  / target["protein"]
    carb_err = (calc_carbs   - target["carbs"])    / target["carbs"]
    fat_err = (calc_fat      - target["fat"])      / target["fat"]

    return np.array([cal_err, pro_err, carb_err, fat_err]) * 10
```

**Weight = 10**: Nhan sai so voi 10 de tang do nhay cua optimizer,
giup no "can than" hon khi dieu chinh gram.

### 4.4 Xu ly ket qua

```python
for i, qty in enumerate(result.x):
    grams = round(qty * 100)      # Chuyen tu don vi 100g sang gram
    if grams >= 30:                # Loai bo mon < 30g (khong thuc te)
        item["calculated_grams"] = grams
        item["calculated_calories"] = round(qty * food[i]["calories"], 1)
        item["calculated_protein"]  = round(qty * food[i]["protein"], 1)
        item["calculated_carbs"]    = round(qty * food[i]["carbs"], 1)
        item["calculated_fat"]      = round(qty * food[i]["fat"], 1)
```

### 4.5 Signature

```python
@staticmethod
def optimize_meal(
    available_foods: List[Dict],    # [{"name": ..., "calories": ..., "protein": ..., "carbs": ..., "fat": ...}]
    target_macros: Dict[str, float] # {"calories": ..., "protein": ..., "carbs": ..., "fat": ...}
) -> List[Dict]
```

Moi phan tu trong `available_foods` chua thong tin dinh duong **tren 100g**.

Tra ve list dict voi cac truong bo sung:
- `calculated_grams`: So gram toi uu
- `calculated_calories`: Calories tai gram do
- `calculated_protein`: Protein tai gram do
- `calculated_carbs`: Carbs tai gram do
- `calculated_fat`: Fat tai gram do

### 4.6 Bounds va Constraints

| Tham so         | Gia tri | Y nghia                                  |
|-----------------|---------|------------------------------------------|
| x0              | 1.0     | Khoi tao moi mon 100g                    |
| lower bound     | 0.3     | Toi thieu 30g (thuc te)                  |
| upper bound     | 4.0     | Toi da 400g (thuc te)                    |
| min output      | 30g     | Loai bo mon duoi 30g khoi ket qua        |

### 4.7 Vi du

```python
foods = [
    {"name": "Ga luoc",    "calories": 165, "protein": 31, "carbs": 0,  "fat": 3.6},
    {"name": "Com gao lut","calories": 123, "protein": 2.7,"carbs": 25, "fat": 1},
    {"name": "Rau muong",  "calories": 19,  "protein": 2.6,"carbs": 3.1,"fat": 0.3},
]

targets = {"calories": 600, "protein": 50, "carbs": 70, "fat": 15}

result = NutritionService.optimize_meal(foods, targets)
# Ket qua co the la:
# [
#   {"name": "Ga luoc",     "calculated_grams": 150, "calculated_calories": 247.5, ...},
#   {"name": "Com gao lut", "calculated_grams": 280, "calculated_calories": 344.4, ...},
#   {"name": "Rau muong",   "calculated_grams": 80,  "calculated_calories": 15.2, ...},
# ]
```

---

## 5. Cach service nay duoc su dung trong Workflow

Trong `NutritionWorkflowService`, NutritionService duoc goi tai 2 diem chinh:

### 5.1 Tinh targets (_compute_targets)
```python
tdee = NutritionService.calculate_tdee(age, gender, weight, height, activity_level)
macros = NutritionService.get_macro_targets(tdee, goal)
```

### 5.2 Toi uu bua an (_build_rule_based_plan_json)
```python
# Cho tung bua:
optimized = NutritionService.optimize_meal(
    optimization_input,     # Subset candidates da chon
    {
        "calories": meal_target["calories"],
        "protein": meal_target["protein_g"],
        "carbs": meal_target["carbs_g"],
        "fat": meal_target["fat_g"],
    }
)
```

Workflow cung su dung optimize_meal o cap do ca ngay
(`_build_daily_rule_based_plan_json`), toi uu toan bo thuc don
truoc roi phan bo vao cac bua.

---

## 6. Gioi han va luu y

1. **Khong xet vi chat dinh duong** - Chi toi uu 4 macro chinh
   (calories, protein, carbs, fat). Khong xet fiber, vitamin, minerals.

2. **Bounds co dinh** - 30-400g cho moi mon. Co the khong phu hop
   cho moi loai thuc pham (vi du: dau an chi can 15g).

3. **Weight dong deu** - 4 macro duoc weight nhu nhau (x10).
   Co the can dieu chinh theo muc tieu (vi du: protein quan trong
   hon cho gain_muscle).

4. **Khong co constraint ve so mon** - Optimizer co the tra ve
   it mon hon input neu nhieu mon bi duoi 30g.

---

## 7. Lien ket tai lieu

- [NutritionWorkflowService](./nutrition-workflow.md) - Su dung NutritionService
- [CanonicalKnowledgeService](./canonical-knowledge.md) - Cung cap danh sach thuc pham
- [NutritionIntentService](./intent-service.md) - Xac dinh goal cho macro targets
- [BGEEmbeddingService](./embedding-service.md) - Tao embedding cho retrieval
