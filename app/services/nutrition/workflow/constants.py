from datetime import datetime, timezone
# Keyword-like constants stay in ascii-normalized form where possible so the
# runtime can rely on one normalization path instead of duplicating d/đ logic.
MEAL_TEMPLATES = {
    3: [("Breakfast", 0.28), ("Lunch", 0.37), ("Dinner", 0.35)],
    4: [("Breakfast", 0.25), ("Lunch", 0.30), ("Dinner", 0.30), ("Snack", 0.15)],
    5: [
        ("Breakfast", 0.22),
        ("Morning Snack", 0.10),
        ("Lunch", 0.28),
        ("Dinner", 0.28),
        ("Evening Snack", 0.12),
    ],
}

GOAL_MAP = {
    "lose_weight": "lose_weight",
    "cutting": "lose_weight",
    "fat_loss": "lose_weight",
    "lose_fat": "lose_weight",
    "giam_can": "lose_weight",
    "giam_mo": "lose_weight",
    "gain_muscle": "gain_muscle",
    "bulking": "gain_muscle",
    "gain": "gain_muscle",
    "tang_co": "gain_muscle",
    "maintain": "maintain",
    "maintenance": "maintain",
    "giu_can": "maintain",
}

STRATEGY_TO_GOAL_FAMILY = {
    "surplus_balanced": "gain_muscle",
    "surplus_high_protein": "gain_muscle",
    "deficit_balanced": "lose_weight",
    "deficit_high_satiety": "lose_weight",
    "maintenance_balanced": "maintain",
    "maintenance_health_support": "maintain",
    "maintenance_training_support": "maintain",
}

GENDER_MAP = {
    "male": "male",
    "nam": "male",
    "man": "male",
    "female": "female",
    "nu": "female",
    "woman": "female",
}

ACTIVITY_MAP = {
    "sedentary": "sedentary",
    "it_van_dong": "sedentary",
    "light": "light",
    "nhe": "light",
    "moderate": "moderate",
    "vua": "moderate",
    "active": "active",
    "nang": "active",
    "very_active": "very_active",
    "rat_nang": "very_active",
}

DIETARY_MAP = {
    "omnivore": "omnivore",
    "balanced": "omnivore",
    "keto": "omnivore",
    "paleo": "omnivore",
    "an_tap": "omnivore",
    "vegetarian": "vegetarian",
    "an_chay": "vegetarian",
    "vegan": "vegan",
    "thuan_chay": "vegan",
    "pescatarian": "pescatarian",
    "eat_fish": "pescatarian",
}

ALLERGY_MAP = {
    "sua": "dairy",
    "milk": "dairy",
    "dairy": "dairy",
    "trung": "egg",
    "egg": "egg",
    "dau_nanh": "soy",
    "soy": "soy",
    "dau_phong": "peanut",
    "lac": "peanut",
    "peanut": "peanut",
    "hat_dieu": "tree_nut",
    "hanh_nhan": "tree_nut",
    "nut": "tree_nut",
    "mi": "gluten",
    "wheat": "gluten",
    "gluten": "gluten",
    "tom": "shellfish",
    "cua": "shellfish",
    "shellfish": "shellfish",
    "ca": "fish",
    "fish": "fish",
    "me": "sesame",
    "sesame": "sesame",
}

GOAL_RETRIEVAL_GUIDES = {
    "lose_weight": {
        "en": "lean protein high fiber moderate carb whole foods for fat loss",
        "vi": "thực phẩm giảm mỡ giàu đạm, nhiều chất xơ, ít năng lượng, no lâu",
        "macro_focus": "lean protein fiber vegetables satiety low energy density",
    },
    "gain_muscle": {
        "en": "high protein high energy complex carbohydrate foods for muscle gain recovery",
        "vi": "thực phẩm tăng cơ giàu đạm, năng lượng cao, tinh bột phù hợp phục hồi sau tập",
        "macro_focus": "high protein high calorie complex carbs post workout recovery",
    },
    "maintain": {
        "en": "balanced whole foods with protein carbs healthy fats micronutrients",
        "vi": "thực phẩm cân bằng đầy đủ đạm, tinh bột, chất béo tốt, vitamin và khoáng chất",
        "macro_focus": "balanced protein carbs healthy fats micronutrients",
    },
}

STRATEGY_RETRIEVAL_GUIDES = {
    "surplus_balanced": {
        "en": "balanced calorie surplus foods for healthy weight gain",
        "vi": "thực phẩm tăng cân lành mạnh, tăng năng lượng vừa phải, dễ ăn hằng ngày",
        "macro_focus": "balanced calorie surplus practical meals steady weight gain",
    },
    "surplus_high_protein": GOAL_RETRIEVAL_GUIDES["gain_muscle"],
    "deficit_balanced": {
        "en": "balanced calorie deficit foods for steady weight loss",
        "vi": "thực phẩm giảm cân cân bằng, no vừa đủ, dễ duy trì lâu dài",
        "macro_focus": "balanced calorie deficit practical meals sustainable weight loss",
    },
    "deficit_high_satiety": GOAL_RETRIEVAL_GUIDES["lose_weight"],
    "maintenance_balanced": GOAL_RETRIEVAL_GUIDES["maintain"],
    "maintenance_health_support": {
        "en": "healthy balanced whole foods rich in micronutrients and digestion support",
        "vi": "thực phẩm cân bằng, lành mạnh, giàu vi chất, hỗ trợ tiêu hóa",
        "macro_focus": "balanced whole foods micronutrients digestion health support",
    },
    "maintenance_training_support": {
        "en": "balanced protein and carb foods for training support and recovery",
        "vi": "thực phẩm cân bằng hỗ trợ tập luyện, phục hồi và năng lượng ổn định",
        "macro_focus": "balanced protein carbs recovery training support",
    },
}

GOAL_POOL_RULES = {
    "gain_muscle": {
        "pool_limit": 18,
        "protein_anchor_count": 4,
        "carb_anchor_count": 4,
        "healthy_fat_anchor_count": 3,
        "produce_anchor_count": 2,
        "balanced_anchor_count": 3,
    },
    "lose_weight": {
        "pool_limit": 18,
        "protein_anchor_count": 3,
        "carb_anchor_count": 2,
        "healthy_fat_anchor_count": 2,
        "produce_anchor_count": 5,
        "balanced_anchor_count": 2,
    },
    "maintain": {
        "pool_limit": 18,
        "protein_anchor_count": 3,
        "carb_anchor_count": 3,
        "healthy_fat_anchor_count": 2,
        "produce_anchor_count": 3,
        "balanced_anchor_count": 2,
    },
}

COMMON_FOOD_HINTS = {
    "uc ga": ["ga", "thit ga", "thit ga nac", "chicken", "breast"],
    "thit ga": ["ga", "thit ga", "chicken"],
    "trung": ["trung", "egg"],
    "gao": ["com", "rice", "bun tuoi", "pho", "xoi nep", "khoai lang", "nui luoc", "ngo luoc"],
    "com": ["com", "rice", "bun tuoi", "pho", "xoi nep", "khoai lang", "nui luoc", "ngo luoc"],
    "gao lut": ["bun tuoi", "khoai lang", "nui luoc", "ngo luoc", "hat sen", "hat sen tuoi luoc"],
    "rau xanh": ["rau", "cai", "rau muong", "sup lo", "bong cai", "vegetable", "cai ngong", "cai ngong luoc"],
    "dau hu": ["dau hu", "dau phu", "tofu", "soy", "dau nanh", "hat bi do", "hat de cuoi"],
    "dau phu": ["dau phu", "dau hu", "tofu", "soy", "dau nanh", "hat bi do", "hat de cuoi"],
    "dau xanh": ["dau xanh", "dau phu", "tofu", "hat bi do", "xoi do xanh"],
    "dau den": ["dau den", "dau phu", "tofu", "hat bi do", "hat de cuoi", "xoi do xanh"],
    "hat bi do": ["hat bi do", "hat bi o", "hat bi", "pumpkin seed"],
    "khoai": ["khoai", "sweet potato", "potato", "cassava"],
    "yen mach": ["yen mach", "oat", "oats", "hat sen", "hat sen tuoi luoc", "khoai lang", "ngo luoc", "xoi do xanh"],
    "ca": ["ca", "fish", "salmon", "tuna"],
    "thit nac": ["thit", "nac", "bo", "heo", "lon", "thit bo", "thit lon"],
}

GOAL_SUPPORT_HINTS = {
    "gain_muscle": ["bo qua", "hat dieu", "ca trich", "trung ga", "bun tuoi", "xoi nep", "khoai lang", "nui luoc"],
    "lose_weight": ["ca", "thit ga", "trung ga", "dau hu", "ca hoi", "ca thu", "sua chua", "bo qua", "bun tuoi", "khoai lang", "ngo luoc"],
    "maintain": ["trung ga", "dau hu", "ca hoi", "sua chua", "bun tuoi", "khoai lang", "nui luoc"],
}

DIET_LOCAL_SUPPLEMENT_HINTS = {
    "vegan": [
        "dau phu",
        "tofu",
        "hat bi do",
        "hat dieu",
        "hat de cuoi",
        "hat huong duong",
        "hat macca",
        "hat oc cho",
        "hat sen tuoi luoc",
        "khoai lang",
        "ngo luoc",
    ],
    "vegetarian": [
        "dau phu",
        "tofu",
        "trung ga",
        "hat bi do",
        "hat dieu",
        "hat macca",
        "hat oc cho",
        "sua chua",
        "khoai lang",
    ],
    "pescatarian": [
        "ca hoi",
        "ca ngu",
        "ca trich",
        "trung ga",
        "hat dieu",
        "hat macca",
        "hat oc cho",
        "khoai lang",
        "bo qua",
    ],
}

DIET_RETRIEVAL_PROTEIN_HINTS = {
    "vegan": ["dau phu", "hat bi do", "hat de cuoi", "dau xanh"],
    "vegetarian": ["dau phu", "trung", "hat bi do", "dau xanh"],
    "pescatarian": ["ca hoi", "ca ngu", "trung", "ca"],
}

COOKED_STAPLE_SUPPORT_HINTS = [
    "bun tuoi",
    "pho",
    "xoi nep",
    "khoai lang",
    "nui luoc",
    "ngo luoc",
    "ngo hap",
    "ngo nuong",
]

RAW_STAPLE_HINTS = {"gao", "com", "rice"}

RETRIEVAL_EXPECTED_ROLE_TAGS = {
    "surplus_balanced": ["protein_anchor", "carb_anchor"],
    "surplus_high_protein": ["protein_anchor", "carb_anchor", "post_workout_friendly"],
    "deficit_balanced": ["protein_anchor", "produce_support", "post_workout_friendly"],
    "deficit_high_satiety": ["protein_anchor", "produce_support", "post_workout_friendly"],
    "maintenance_balanced": ["protein_anchor", "carb_anchor", "produce_support"],
    "maintenance_health_support": ["protein_anchor", "produce_support"],
    "maintenance_training_support": ["protein_anchor", "carb_anchor", "post_workout_friendly"],
}

RETRIEVAL_SHARED_ANCHORS = {
    "carb": ["gao", "yen mach", "khoai", "nui"],
    "produce": ["rau xanh", "rau luoc", "trai cay"],
}

RETRIEVAL_BALANCED_ANCHORS = {
    "omnivore": ["trung", "ca", "sua chua"],
    "pescatarian": ["ca", "trung", "sua chua"],
    "vegetarian": ["trung", "dau hu", "sua chua"],
    "vegan": ["dau hu", "dau xanh", "dau lang"],
}

RETRIEVAL_STRATEGY_DIET_ANCHORS = {
    "surplus_balanced": {
        "omnivore": {"protein": ["thit ga", "trung", "ca", "bo nac"], "balanced": ["trung", "ca"]},
        "pescatarian": {"protein": ["ca", "ca hoi", "ca ngu", "trung"], "balanced": ["ca", "trung"]},
        "vegetarian": {"protein": ["dau hu", "dau nanh", "trung", "sua chua"], "balanced": ["trung", "dau hu"]},
        "vegan": {"protein": ["dau hu", "dau nanh", "dau lang", "dau xanh"], "balanced": ["dau hu", "dau xanh"]},
    },
    "surplus_high_protein": {
        "omnivore": {"protein": ["uc ga", "trung", "ca ngu", "bo nac"], "balanced": ["trung", "ca ngu"]},
        "pescatarian": {"protein": ["ca ngu", "ca hoi", "ca", "trung"], "balanced": ["ca ngu", "trung"]},
        "vegetarian": {"protein": ["dau hu", "dau nanh", "trung", "sua chua"], "balanced": ["trung", "dau hu"]},
        "vegan": {"protein": ["dau hu", "dau nanh", "dau lang", "dau xanh"], "balanced": ["dau hu", "dau lang"]},
    },
    "deficit_balanced": {
        "omnivore": {"protein": ["thit ga", "ca", "trung", "bo nac"], "balanced": ["ca", "trung"]},
        "pescatarian": {"protein": ["ca", "ca hoi", "ca ngu", "trung"], "balanced": ["ca", "trung"]},
        "vegetarian": {"protein": ["dau hu", "trung", "sua chua", "dau nanh"], "balanced": ["trung", "dau hu"]},
        "vegan": {"protein": ["dau hu", "dau lang", "dau xanh", "dau nanh"], "balanced": ["dau hu", "dau lang"]},
    },
    "deficit_high_satiety": {
        "omnivore": {"protein": ["thit ga", "ca", "trung", "bo nac"], "balanced": ["ca", "trung"]},
        "pescatarian": {"protein": ["ca", "ca hoi", "ca ngu", "trung"], "balanced": ["ca", "trung"]},
        "vegetarian": {"protein": ["dau hu", "trung", "sua chua", "dau nanh"], "balanced": ["trung", "dau hu"]},
        "vegan": {"protein": ["dau hu", "dau lang", "dau xanh", "dau nanh"], "balanced": ["dau hu", "dau xanh"]},
    },
    "maintenance_balanced": {
        "omnivore": {"protein": ["thit ga", "trung", "ca", "bo nac"], "balanced": ["trung", "ca"]},
        "pescatarian": {"protein": ["ca", "ca hoi", "ca ngu", "trung"], "balanced": ["ca", "trung"]},
        "vegetarian": {"protein": ["dau hu", "trung", "sua chua", "dau nanh"], "balanced": ["trung", "dau hu"]},
        "vegan": {"protein": ["dau hu", "dau nanh", "dau lang", "dau xanh"], "balanced": ["dau hu", "dau xanh"]},
    },
    "maintenance_health_support": {
        "omnivore": {"protein": ["thit ga", "ca", "trung", "sua chua"], "balanced": ["thit ga", "ca", "trung"]},
        "pescatarian": {"protein": ["ca", "trung", "sua chua", "ca hoi"], "balanced": ["ca", "trung", "sua chua"]},
        "vegetarian": {"protein": ["trung", "dau hu", "sua chua", "dau nanh"], "balanced": ["trung", "dau hu", "sua chua"]},
        "vegan": {"protein": ["dau hu", "dau xanh", "dau lang", "dau nanh"], "balanced": ["dau hu", "dau xanh"]},
    },
    "maintenance_training_support": {
        "omnivore": {"protein": ["thit ga", "trung", "ca", "bo nac"], "balanced": ["trung", "ca"]},
        "pescatarian": {"protein": ["ca", "ca hoi", "ca ngu", "trung"], "balanced": ["ca", "trung"]},
        "vegetarian": {"protein": ["dau hu", "trung", "sua chua", "dau nanh"], "balanced": ["trung", "dau hu"]},
        "vegan": {"protein": ["dau hu", "dau nanh", "dau lang", "dau xanh"], "balanced": ["dau hu", "dau lang"]},
    },
}

RETRIEVAL_ALLERGY_ANCHOR_BLOCKLIST = {
    "fish": {"ca", "ca hoi", "ca ngu"},
    "soy": {"dau nanh", "dau hu", "dau phu", "tofu"},
    "dairy": {"sua chua"},
    "egg": {"trung"},
}

RETRIEVAL_QUERY_STOPWORDS = {
    "an",
    "cho",
    "can",
    "dang",
    "de",
    "duoc",
    "hay",
    "hon",
    "khong",
    "la",
    "lam",
    "mon",
    "mot",
    "muon",
    "nhung",
    "nhe",
    "the",
    "thuc",
    "thucdon",
    "toi",
    "tot",
    "uu",
    "tien",
    "va",
    "voi",
}

GENERIC_SUPPORT_HINTS = {
    "rau",
    "rau xanh",
    "rau luoc",
    "trai cay",
    "hoa qua",
    "gao",
    "com",
    "yen mach",
    "khoai",
}

LOW_PRACTICALITY_KEYWORDS = [
    "hat tieu",
    "bot ",
    " bot",
    "ruoc",
    ", kho",
    " kho,",
    " kho ",
    "nuoc mam",
    "gia vi",
    "men bia",
    " muoi",
]

PREFERRED_PROTEIN_KEYWORDS = [
    "ga",
    "chicken",
    "bo",
    "beef",
    "heo",
    "lon",
    "thit",
    "trung",
    "egg",
    "ca ",
    "fish",
    "salmon",
    "tuna",
    "sua",
    "milk",
    "yogurt",
    "dau hu",
    "dau phu",
    "tofu",
    "dau nanh",
    "dau xanh",
    "dau den",
    "soy",
    "hat bi do",
    "hat bi o",
    "hat de cuoi",
    "hat huong duong",
]

PREFERRED_CARB_KEYWORDS = [
    "gao",
    "rice",
    "com",
    "khoai",
    "sweet potato",
    "potato",
    "ngo",
    "corn",
    "yen mach",
    "oat",
    "mi",
    "bun",
    "pho",
    "mien",
    "san",
    "cassava",
]

REALISM_HARD_BLOCK_NAME_KEYWORDS = [
    "toi ",
    "hanh ",
    "ot ",
    "hat tieu",
    "nuoc mam",
    "nuoc tuong",
    "gia vi",
    "duong ",
    "keo",
    "mut ",
    "men bia",
    "tim ",
    "song",
]

REALISM_HARD_BLOCK_GROUP_KEYWORDS = [
    "gia vi",
    "nuoc cham",
    "dau, mo, bo",
]

REALISM_DISCOURAGED_NAME_KEYWORDS = [
    "long ",
    "tim ",
    "gan ",
    "me ",
    "tiet ",
    "trung ca",
    "con ",
    "ruoc",
]

AFFORDABLE_FOOD_KEYWORDS = [
    "ga",
    "trung",
    "gao",
    "com",
    "dau hu",
    "rau",
    "khoai",
    "ca",
]

COMMON_MEAL_FOOD_KEYWORDS = [
    "ga",
    "trung",
    "gao",
    "com",
    "khoai",
    "dau hu",
    "rau",
    "ca",
    "thit",
    "yen mach",
]

MAIN_MEAL_NAMES = {"breakfast", "lunch", "dinner"}

HEALTHY_BALANCED_MEAL_PHRASES = {
    "an lanh manh",
    "lanh manh",
    "song khoe",
    "tot cho suc khoe",
    "nhe bung",
    "de an",
    "can bang",
}

PORTION_CAP_BY_NAME_KEYWORDS = {
    "rong bien": 25,
    "ngo sen": 100,
    "rau khoai lang": 140,
    "la san": 120,
    "hat sen": 120,
    "hat macca": 25,
    "hat oc cho": 25,
    "hat de cuoi": 25,
    "hat huong duong": 25,
    "hat bi do": 25,
    "hat bi o": 25,
    "hat dieu": 25,
    "lac": 25,
    "nho": 100,
    "mit": 100,
    "dau tay": 120,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
