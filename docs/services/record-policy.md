# Nutrition Record Policy - Chinh sach lam giau du lieu thuc pham

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/nutrition_record_policy.py`

---

## Tong quan

`NutritionRecordPolicy` la module chiu trach nhiem **lam giau (enrich)** ban ghi thuc pham/mon an
truoc khi dua vao he thong meal planning. Module nay thuc hien:

1. Chuan hoa ten mon an va phat hien cach che bien
2. Suy luan thanh phan dinh duong tu ten
3. Danh gia muc do san sang cho meal plan (meal readiness)
4. Gan nhan vai tro bua an (meal role tags)
5. Tinh diem xep hang va trang thai QC

Module nay **khong phu thuoc LLM** - toan bo logic la rule-based, deterministic.

## 1. Cac bang du lieu tham chieu (Constants)

### 1.1 PREPARATION_PATTERNS

Danh sach 10 kieu che bien duoc nhan dien tu ten mon an:

| Style | Keywords nhan dien |
|-------|-------------------|
| `boiled` | luoc, boiled |
| `grilled` | nuong, grilled |
| `fried` | chien, ran, fried |
| `stir_fried` | xao, stir fried, stir-fried |
| `steamed` | hap, steamed |
| `braised` | kho, om, braised |
| `roasted` | quay, roasted |
| `soup` | canh, sup, soup |
| `porridge` | chao, porridge |
| `raw` | tuoi, raw, fresh |

### 1.2 PORTION_DEFAULTS_BY_TAXONOMY

Khoi luong mac dinh (gram) theo nhom taxonomy level 2, ap dung khi ban ghi khong co `portion_g`:

- `noodle_and_soup_dishes`: 380g | `rice_and_porridge_dishes`: 320g
- `soups_and_broths`: 300g | `stir_fried_dishes`: 240g | `drinks`: 240g
- `shellfish_and_mollusks`: 220g | `desserts`: 180g | `ready_made_foods`: 180g
- `cakes_pastries_snacks`: 120g | `other_dishes`: 240g

### 1.3 INGREDIENT_HINT_PATTERNS

23 loai nguyen lieu voi keyword tieng Viet (khong dau) + tieng Anh. Dung de suy luan thanh phan
chinh tu ten mon an khi khong co `dish_components`. VD: `uc ga` (tu "uc ga", "chicken breast"),
`ca` (tu "ca ", "fish", "salmon"), `rau xanh` (tu "rau", "cai", "vegetable").

### 1.4 Cac bang keyword phan loai

| Hang so | Muc dich | Vi du keyword |
|---------|----------|---------------|
| `CONDIMENT_KEYWORDS` | Nhan dien gia vi / phu lieu | toi, hanh, ot, muoi, gia vi, nuoc mam, nuoc tuong |
| `OFFAL_KEYWORDS` | Nhan dien noi tang / dac san | long, tim, gan, tiet, giblet, roe |
| `DESSERT_KEYWORDS` | Nhan dien do ngot / banh | banh, che, kem, caramen, keo, mut |
| `SAVORY_BAKERY_KEYWORDS` | Phan biet banh man (khong bi block) | banh bao, banh cuon, banh beo, banh gio, banh chung |
| `AFFORDABLE_KEYWORDS` | Tang diem cho thuc pham binh dan | ga, trung, gao, com, khoai, dau hu, rau, ca |

---

## 2. Ham tien ich (Utilities)

### 2.1 ascii_normalize(value)

Chuan hoa text ve dang ASCII lowercase, loai bo dau tieng Viet.
- Input: bat ky gia tri nao (string, None, so)
- Output: chuoi ASCII lowercase, khoang trang duoc don lai
- Su dung `unicodedata.normalize("NFKD")` roi encode ASCII

### 2.2 safe_float(value, default=0.0)

Chuyen doi an toan sang float, tra ve `default` neu:
- Gia tri la `None` hoac chuoi rong
- Khong parse duoc (TypeError, ValueError)
- Gia tri la `NaN` hoac `Inf`

### 2.3 normalize_component_list(raw_components)

Chuan hoa danh sach thanh phan mon an:
- Ho tro input la list cua string hoac list cua dict (key: `name`, `ingredient`, `food_name`)
- Loai bo trung lap (dedup theo ascii_normalize)
- Tra ve list chuoi da lam sach

---

## 3. Cac ham xu ly ten mon an

### 3.1 preparation_style(name)

Tra ve kieu che bien cua mon an dua tren ten.

```python
preparation_style("Ga nuong mat ong") -> "grilled"
preparation_style("Rau xao toi") -> "stir_fried"
preparation_style("Salad") -> None  # Khong nhan dien duoc
```

### 3.2 canonical_name_key(name)

Tao khoa chuan cho ten mon an:
1. Chuan hoa ASCII
2. Loai bo noi dung trong ngoac don `(...)`
3. Thay cac ky tu dac biet `,;:/-` bang khoang trang
4. Don khoang trang

### 3.3 meal_family_key(name)

Tao khoa "ho mon an" - giong `canonical_name_key` nhung **loai bo tu chi kieu che bien**.
Giup gom mon cung loai (vd: "ga luoc", "ga nuong", "ga hap" -> cung family).

### 3.4 exact_dedup_key(record)

Tao khoa dedup chinh xac tu nhieu truong:
```
entity_type | canonical_name | portion_basis | taxonomy_level_2 | energy_kcal | protein_g | carbs_g | fat_g
```

Dung de phat hien ban ghi trung lap hoan toan.

---

## 4. Suy luan thong tin

### 4.1 infer_ingredient_hints(record)

**Uu tien 1:** Lay tu `dish_components` (neu co) -> chuan hoa qua `normalize_component_list()`, lay toi da 8 thanh phan.

**Uu tien 2:** Suy luan tu ten mon an bang cach doi chieu voi `INGREDIENT_HINT_PATTERNS`.
Quet qua cac truong: `name`, `name_en`, `group_name`, `category_name_en`.

Ket qua duoc dedup va gioi han 8 phan tu.

### 4.2 infer_serving_size(record)

Tra ve tuple `(gram, source, confidence)`:

| Dieu kien | Gram | Source | Confidence |
|-----------|------|--------|------------|
| Co `portion_g` > 0 | Gia tri goc | `"source"` | `"high"` |
| entity_type = "food" | `None` | `"per_100g_default"` | `"high"` |
| Co trong PORTION_DEFAULTS_BY_TAXONOMY | Gia tri bang | `"taxonomy_default"` | `"medium"` |
| energy >= 350 | 220.0 | `"energy_heuristic"` | `"low"` |
| energy >= 180 | 180.0 | `"energy_heuristic"` | `"low"` |
| Mac dinh | 150.0 | `"generic_dish_default"` | `"low"` |

### 4.3 infer_meal_role_tags(record)

Gan nhan vai tro bua an dua tren macro va taxonomy:

| Tag | Dieu kien |
|-----|-----------|
| `protein_anchor` | protein >= 12g |
| `carb_anchor` | carbs >= 18g |
| `produce_support` | ten chua "rau", fiber >= 3g, hoac co tag "produce" |
| `snack` | 80 <= energy <= 260, carbs >= 10, fat <= 15 |
| `post_workout_friendly` | protein >= 15 va carbs >= 15 |
| `pre_workout_friendly` | carbs >= 20 va fat <= 12 |
| `main_meal` | Dish thuoc nhom noodle/rice/stir_fried |
| `lunch_dinner_friendly` | Dish thuoc nhom noodle/rice/stir_fried |
| `breakfast_friendly` | Food co keyword: yen mach, banh mi, trung, sua, yogurt |
| `dessert` | Dish thuoc nhom desserts/cakes |
| `beverage` | Dish thuoc nhom drinks |

---

## 5. Danh gia Meal Readiness

### 5.1 _practicality_penalties(record)

Tra ve hai danh sach: `hard_penalties` (chan hoan toan) va `soft_penalties` (giam diem).

**Hard penalties** (ban ghi bi block):
- `condiment_like`: La gia vi (granularity = "condiment" hoac match CONDIMENT_KEYWORDS)
- `specialty_offal_like`: La noi tang (match OFFAL_KEYWORDS)
- `drink_not_meal_component`: La do uong voi protein < 10g
- `dessert_category`: Thuoc taxonomy desserts_and_sweets hoac desserts
- `bakery_snack_like`: Thuoc bakery_and_snacks ma khong phai banh man giau protein
- `missing_name`: Khong co ten

**Soft penalties** (giam diem):
- `drink_as_snack_only`: Do uong co protein >= 10g
- `savory_bakery_limited`: Banh man voi protein >= 8 va carbs >= 15
- `dessert_like`: Ten match DESSERT_KEYWORDS nhung khong thuoc taxonomy ngot
- `light_food_not_meal`: Thuc pham nhe (energy < 120, protein < 6, carbs < 25)

### 5.2 evaluate_meal_readiness(record)

Tinh diem meal readiness (0.0 - 1.0) theo cong thuc:

```
score = 0.34 * quality
      + 0.20 * macro_complete     (ty le macro co du lieu: 0/4 -> 4/4)
      + 0.32 * min(role_score, 1.0)
      + macro_density_bonus       (thuong cho protein/carbs/energy tot)
      + affordability_bonus       (+0.06 neu la thuc pham binh dan)
      - 0.18 * so_soft_penalties
      - 0.45 * so_hard_penalties
```

### 5.3 Phan tier

| Tier | Dieu kien | planner_rank_weight |
|------|-----------|---------------------|
| `core` | score >= 0.78, khong co hard penalty | 1.0 |
| `support` | score >= 0.58 | 0.82 |
| `snack` | score >= 0.42 | 0.64 |
| `discouraged` | score < 0.42 hoac dessert_like khong phai snack | 0.18 |
| `blocked` | co hard penalty hoac score < 0.35 | 0.0 |

Chi cac tier `core`, `support`, `snack` duoc coi la `meal_ready = True` va duoc phep tham gia
vao he thong retrieval (`production_retrieval_enabled = True`).

---

## 6. Ham tong hop: enrich_meal_ready_record(record)

Day la ham entry-point chinh. Nhan vao mot `dict` ban ghi thuc pham va tra ve ban ghi
da duoc lam giau voi cac truong bo sung:

- **Serving:** `portion_g`, `portion_g_source`, `serving_size_confidence`
- **Ten:** `preparation_style`, `canonical_name_key`, `meal_family_key`, `exact_dedup_key`
- **Thanh phan:** `ingredient_components_normalized`, `ingredient_hints`, `ingredient_detail_source`
- **Vai tro:** `meal_role_tags`, `meal_role_primary`
- **Readiness:** `meal_readiness_score`, `meal_readiness_tier`, `meal_ready`
- **Planner:** `planner_rank_weight`, `production_retrieval_enabled`, `production_block_reasons`
- **QC:** `meal_ready_exclusion_codes`

---

## 7. Luu y thiet ke

- **Deterministic:** Toan bo logic rule-based, khong goi LLM. Cung input luon cho cung output.
- **Tieng Viet first:** Pattern thiet ke cho ten mon Viet (khong dau).
- **An toan:** `safe_float()` khong crash khi du lieu thieu hoac sai format.
- **Dedup nhieu tang:** `exact_dedup_key` cho trung lap chinh xac, `meal_family_key` nhom bien the.

---

## Tai lieu lien quan

- [Tong quan kien truc](../architecture/overview.md)
- [RAG Pipeline](../architecture/rag-pipeline.md)
- [LLM Service](./llm-service.md)
- [Evaluation Service](./evaluation-service.md)
- [Cache va State Management](./cache-state.md)
