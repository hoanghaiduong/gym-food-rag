# Huong dan Dong gop

> Cap nhat lan cuoi: 2026-04-06

## Git Workflow

### Branching Strategy

```
main (production)
  |
  +-- develop (staging)
       |
       +-- feature/xyz   (tinh nang moi)
       +-- fix/abc        (sua loi)
       +-- docs/xyz       (cap nhat tai lieu)
       +-- refactor/xyz   (tai cau truc)
```

### Quy trinh

1. Tao branch tu `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/ten-tinh-nang
   ```

2. Lam viec va commit:
   ```bash
   git add <files>
   git commit -m "feat: mo ta ngan gon"
   ```

3. Push va tao PR:
   ```bash
   git push origin feature/ten-tinh-nang
   # Tao Pull Request tren GitHub
   ```

4. Code review & merge vao `develop`

---

## Commit Message Convention

Su dung **Conventional Commits**:

```
<type>: <mo ta ngan gon>

[body - optional]
[footer - optional]
```

### Types

| Type | Muc dich | Vi du |
|------|----------|-------|
| `feat` | Tinh nang moi | `feat: them endpoint goi y 5 bua` |
| `fix` | Sua loi | `fix: sua loi TDEE tinh sai cho nu` |
| `docs` | Tai lieu | `docs: them huong dan cai dat` |
| `refactor` | Tai cau truc | `refactor: tach NutritionWorkflowService` |
| `perf` | Hieu nang | `perf: cache embedding results` |
| `test` | Tests | `test: them test case cho vegetarian` |
| `chore` | Bao tri | `chore: cap nhat dependencies` |
| `style` | Format code | `style: chay black formatter` |

---

## Cau truc Du an (Khi them code moi)

### Them API Endpoint moi

1. Tao/sua router trong `app/api/v3/`
2. Tao Pydantic schemas trong `app/schemas/`
3. Mount router trong `app/api/router.py`
4. Cap nhat docs trong `docs/api/`

### Them Service moi

1. Tao file trong `app/services/`
2. Su dung **singleton pattern** (module-level instance)
3. Dang ky dependencies trong endpoint hoac service khac
4. Cap nhat docs trong `docs/services/`

### Them Database Table moi

1. Tao file trong `app/db/tables/`
2. Import trong `app/db/tables/__init__.py`
3. Cap nhat `app/db/seeds.py` neu can
4. Cap nhat docs trong `docs/database/`

---

## Quy uoc ten

| Muc | Convention | Vi du |
|-----|-----------|-------|
| Python files | snake_case | `nutrition_service.py` |
| Classes | PascalCase | `NutritionWorkflowService` |
| Functions | snake_case | `calculate_tdee()` |
| Constants | UPPER_SNAKE | `MEAL_TEMPLATES` |
| API routes | kebab-case | `/api/v3/nutrition/recommendation` |
| DB tables | snake_case | `chat_sessions` |
| Env vars | UPPER_SNAKE | `LLM_BACKEND` |

---

## Testing

### Chay Test thu cong

```powershell
# Test API voi curl
python -m scripts.test_nutrition_cases \
  --username admin --password admin

# Test embedding
python -m scripts.check_native_rerank

# Test Ollama connection
python -m scripts.ollama_smoke

# Test import
python -m scripts.debug_import
```

### Kiem tra Chat luong Du lieu

```powershell
python -m scripts.qc_nutrition_kb
```

---

## Files Can Biet

| File/Dir | Muc dich | Khi nao sua |
|----------|----------|-------------|
| `app/main.py` | App factory | Them middleware, mount router |
| `app/api/router.py` | Central router | Mount router moi |
| `app/core/config.py` | Settings | Them env var moi |
| `app/db/seeds.py` | Seed data | Them permissions/roles |
| `requirements.txt` | Dependencies | Them package moi |
| `.env.example` | Env template | Them env var moi |

---

## Lien ket

- [Code Style](code-style.md)
- [Kien truc tong quan](../architecture/overview.md)
- [Cau hinh](../getting-started/configuration.md)
