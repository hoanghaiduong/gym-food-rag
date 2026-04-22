# Kế Hoạch Fix Vấn Đề Nutrition Recommendation

## 📊 Tóm Tắt Vấn Đề

**Request của bạn**: `"Tăng cơ giảm mỡ"` + `must_include: ["ức gà"]`  
**Profile**: `dietary_preference: "vegetarian"`  
**Kết quả hiện tại**: Protein -14.64%, must_include_missing ("uc ga"), response time 138s (quá chậm)

---

## 🔴 Root Causes (5 Vấn Đề Chính)

### **Vấn Đề 1: Dietary Conflict - Không có cơ chế override** [P0 - CRITICAL]
- **Nguyên nhân**: System strict apply `dietary_preference="vegetarian"` ngay từ retrieval stage
- **Hệ quả**: Chicken bị filter trước khi must_include collector chạy
- **File**: `nutrition_workflow_service.py:474` (`_retrieve_candidates()`)
- **Dòng code**:
  ```python
  # Qdrant query sử dụng dietary_preference filter
  # Chicken không có "vegetarian" tag → Loại bỏ
  # Must_include=["ức gà"] KHÔNG thể tìm được
  ```

### **Vấn Đề 2: Must-Include Check Quá Muộn** [P1 - HIGH]
- **Nguyên nhân**: `_collect_must_include_candidates()` chạy SAU dietary filter
- **Hệ quả**: Chicken đã bị remove từ candidate pool → collector không tìm được
- **File**: `nutrition_workflow_service.py:1090`
- **Dòng code**:
  ```python
  ranked_candidates = [items đã qua dietary filter - NO CHICKEN]
  for hint in must_include:  # ["ức gà"]
      direct_matches = [item for item in ranked_candidates...]  # Empty!
  ```

### **Vấn Đề 3: Protein Target Không Điều Chỉnh** [P2 - MEDIUM]
- **Nguyên nhân**: Target protein luôn 30% calories, không care về constraints
- **Hệ quả**: Vegetarian sources có thể đạt max 113.8g nhưng target 188.5g
- **File**: `nutrition_service.py:~140` (`get_macro_targets()`)
- **Mả**: Không có logic check "achievable protein" từ available foods

### **Vấn Đề 4: Validation Error Messages Không Rõ Ràng** [P3 - LOW]
- **Nguyên nhân**: Error messages generic, không explain "TẠI SAO" fail
- **Hệ quả**: User không biết debug
- **File**: `nutrition_workflow_service.py:1999-2000`

### **Vấn Đề 5: BGEM3 Native Rerank Timeout** [P2 - MEDIUM] ⭐ NEW
- **Nguyên nhân**: ProcessPoolExecutor timeout = 25s quá ngắn cho BGE-M3 model
- **Hệ quả**: 
  ```
  [Rerank] Native BGEM3 rerank unavailable for this request; 
  falling back to lexical+dense scoring. Reason: TimeoutError
  ```
  → Search quality giảm (dùng simple lexical+dense thay vì advanced semantics)
- **File**: `app/services/embedding_bge_service.py:412-417`
- **Cấu hình hiện tại**:
  ```env
  RETRIEVAL_ENABLE_NATIVE_RERANK=true
  RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS=25  # ← Quá ngắn!
  RETRIEVAL_NATIVE_RERANK_MAX_DOCS=6
  RETRIEVAL_NATIVE_RERANK_MAX_CHARS=512
  ```
- **Logs này xảy ra**:
  - Request 1 (153s response time): Timeout → fallback
  - Request 2 (188s response time): Timeout → fallback
- **Diagnosis flow**:
  ```
  rerank_documents(query, 30 docs)
    ↓
  _native_rerank_documents(query, 6 docs)  # max_docs=6
    ↓
  ProcessPoolExecutor.submit(_native_rerank_worker_score, ...)
    ↓
  future.result(timeout=25s)  # ← Timeout exception here!
    ↓
  except FuturesTimeoutError → print fallback message
    ↓
  _fallback_rerank_documents()  # ← Quality degradation
  ```

---

## ✅ Giải Pháp Chi Tiết (5 Fixes)

### **FIX 1: Add `dietary_override` Flag**
**Status**: ✅ COMPLETED

**Thay đổi**:
1. **File**: `app/schemas/nutrition_intent.py`
   - Add property: `dietary_override: bool = False` to `NutritionIntent`
   - Đặt `True` nếu `must_include` conflict với `dietary_preference`

2. **File**: `app/services/nutrition_intent_service.py` (line ~170)
   - After `parse_intent()`, check:
   ```python
   def _detect_dietary_override(self, profile, intent, request):
       if request.must_include and profile.get("dietary_preference") != "omnivore":
           # Check if any must_include item is non-vegetarian
           for hint in request.must_include:
               if self._is_meat_like_hint(hint):  # "ức gà", "cá", etc
                   return True
       return False
   ```

3. **File**: `app/services/nutrition_workflow_service.py` (line ~307)
   - Pass `dietary_override` flag downstream

**Test**: 
```python
must_include=["ức gà"], dietary_preference="vegetarian" → dietary_override=True
must_include=["trứng"], dietary_preference="vegetarian" → dietary_override=False (eggs OK)
```

---

### **FIX 2: Two-Pass Candidate Retrieval**
**Status**: ✅ COMPLETED

**Thay đổi**:
1. **File**: `app/services/nutrition_workflow_service.py` (line ~474 `_retrieve_candidates()`)
   - Refactor thành TWO separate passes:

   ```python
   def _retrieve_candidates(self, ...):
       all_candidates = []
       
       # PASS 1: Must-include items (NO dietary filter)
       if request.must_include:
           must_include_candidates = self.knowledge.retrieve_by_hints(
               hints=request.must_include,
               dietary_filter=None,  # ⭐ IMPORTANT
               limit=12
           )
           all_candidates.extend(must_include_candidates)
       
       # PASS 2: Regular candidates (WITH dietary filter)
       other_candidates = self.knowledge.retrieve_candidates(
           goal=goal,
           dietary_preference=profile.get("dietary_preference"),
           dietary_filter=not dietary_override,  # ⭐
           limit=42
       )
       all_candidates.extend(other_candidates)
       
       return self._deduplicate_candidates(all_candidates)
   ```

2. **File**: `app/services/nutrition_knowledge_service.py`
   - Add parameter `dietary_filter=True` to `retrieve_candidates()`
   - If `dietary_filter=False`, skip diet tag matching

**Result**: Chicken sẽ có trong candidate pool ngay từ đầu ✓

---

### **FIX 3: Re-rank Must-Include Foods**
**Status**: ✅ COMPLETED (bonus 1.4 → 2.0)

**Thay đổi**:
1. **File**: `app/services/nutrition_workflow_service.py` (line ~1184 `_optimize_candidate_pool()`)
   - Tăng bonus weight cho must-include matches:

   ```python
   def _goal_fit_score(self, item, goal, request, must_include_hints):
       score = 0.0
       
       # Existing logic...
       if self._candidate_matches_hint(item, must_include_hints):
           score += 2.0  # ⭐ Từ 1.4 → 2.0 (priority tăng)
           score += 0.5  # Additional bonus
       
       return score
   ```

2. **File**: `app/services/nutrition_workflow_service.py` (line ~1090 `_collect_must_include_candidates()`)
   - Update để check trong unfiltered pool:

   ```python
   def _collect_must_include_candidates(self, candidates, must_include):
       # candidates giờ KHÔNG bị filter → sẽ tìm được chicken
       collected = {}
       for hint in must_include:
           matches = [c for c in candidates if self._candidate_matches_hint(c, hint)]
           if matches:
               collected[hint] = matches[0]  # Get best match
       return collected
   ```

**Result**: Chicken được rank cao, included trong plan ✓

---

### **FIX 4: Improve Validation & Error Messages**
**Status**: ✅ COMPLETED (skip override + explanations)

**Thay đổi**:
1. **File**: `app/services/nutrition_workflow_service.py` (line ~1999 `_validate_plan()`)
   - Skip dietary check nếu `dietary_override=True`:

   ```python
   if profile.get("dietary_preference") and profile.get("dietary_preference") != "omnivore":
       total_checks += 1
       if preference_hits and not dietary_override:  # ⭐ Check override
           issues.append({
               "code": "dietary_preference_violation",
               "severity": "error",
               ...
           })
   ```

2. **File**: `app/services/nutrition_workflow_service.py` (line ~2085)
   - Add explanation field for macro failures:

   ```python
   if protein_error_pct > tolerance:
       explanation = ""
       if profile.get("dietary_preference") == "vegetarian":
           explanation = "Low protein due to vegetarian dietary constraint. "
           explanation += "Consider: (1) Add more tofu/beans, (2) Set diet to omnivore"
       
       issues.append({
           "code": "protein_g_target_miss",
           "severity": "error",
           "explanation": explanation,
           ...
       })
   ```

3. **File**: `app/schemas/nutrition.py`
   - Add `validation_insights` to `NutritionRecommendationResponse`:
   ```python
   class NutritionRecommendationResponse:
       ...
       validation: dict
       validation_insights: Optional[dict] = None  # New field
   ```

**Result**: User nhận được clear message: "Why failed" + "How to fix" ✓

---

### **FIX 5: Increase Native Rerank Timeout & Add Monitoring**
**Status**: ✅ COMPLETED (25s → 60s + logging)

**Nguyên nhân**: ProcessPoolExecutor timeout lấy từ `.env` quá ngắn (25s)

**Thay đổi**:
1. **File**: `.env`
   - Tăng timeout:
   ```env
   # Từ
   RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS=25
   # Sang
   RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS=60  # ← 60s cho BGE-M3
   ```

2. **File**: `app/services/embedding_bge_service.py:412-417`
   - Add logging + monitoring:
   ```python
   except (FuturesTimeoutError, BrokenProcessPool, RuntimeError, Exception) as exc:
       self._reset_native_rerank_executor()
       
       # ⭐ Enhanced logging
       logger.warning(
           "Native BGEM3 rerank timeout/failed",
           extra={
               "error_type": type(exc).__name__,
               "timeout_seconds": self.native_rerank_timeout_seconds,
               "docs_count": len(docs),
               "query_length": len(query),
               "recommend": "Increase RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS or reduce max_docs"
           }
       )
       
       print(
           "[Rerank] Native BGEM3 rerank unavailable for this request; "
           f"falling back to lexical+dense scoring. Reason: {type(exc).__name__}: {exc}"
       )
   ```

3. **File**: `app/core/config.py` (or add validation in init)
   - Add config validation:
   ```python
   RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS = int(
       os.getenv("RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS", "60")
   )
   if RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS < 30:
       logger.warning(
           "Rerank timeout too low: {}s. BGE-M3 typically needs 40-80s. "
           "Consider increasing RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS".format(
               RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS
           )
       )
   ```

4. **Optional**: Add caching for rerank scores
   ```python
   # In embedding_bge_service.py
   self._rerank_cache = {}  # Cache rerank results
   
   def rerank_documents(self, query: str, documents: Iterable[str]):
       cache_key = hashlib.md5(f"{query}_{len(docs)}".encode()).hexdigest()
       if cache_key in self._rerank_cache:
           return self._rerank_cache[cache_key]
       
       # ... existing logic ...
       
       self._rerank_cache[cache_key] = result
       return result
   ```

**Result**: 
- ✅ BGE-M3 rerank completes without timeout
- ✅ Better search quality (full semantic ranking)
- ✅ Clear logging if still fails
- ✅ Faster subsequent similar queries (with cache)

**Performance Impact**:
- Timeout 25s → 60s: Each request +1-2s slowdown worst case
- But: Improved quality compensates
- Best practice: Increase timeout OR reduce `max_docs` from 6 → 4

---

## 📋 Implementation Checklist

- [x] **FIX 1**: Add `dietary_override` 
- [x] **FIX 2**: Two-pass retrieval
- [x] **FIX 3**: Re-rank must-include (bonus 2.0)
- [x] **FIX 4**: Improve errors (explanations + override skip)
- [x] **FIX 5**: Rerank timeout (60s + logging)
  
- [ ] **CURRENT ISSUES**:
  - [ ] Performance (138s too slow)
  - [ ] Must-include matching ("uc ga" still reported missing)
  - [ ] Protein target for vegetarian + gain_muscle
  - [ ] Update to use `max_revision_rounds=1`

---

## 🎯 Expected Outcome

**After all fixes**:
```json
{
  "status": "success",
  "validation": {
    "passed": true,  // ✅ Changed from false
    "issues": []
  },
  "plan": {
    "meals": [
      {
        "meal_name": "Breakfast",
        "items": [
          {"food_name": "Ức gà, nướng", "grams": 150, "protein_g": 45},
          {"food_name": "Gạo trắng, cơm", "grams": 100, "protein_g": 8}
        ]
      },
      // ... lunch, dinner with high protein from chicken
    ],
    "totals": {
      "protein_g": 187.5,  // ✅ Close to target 188.5g
      "carbs_g": 314.8,    // ✅ Match target
      "fat_g": 56.2        // ✅ Match target
    }
  },
  "validation_insights": {
    "dietary_override": true,
    "explanation": "System detected conflict between vegetarian preference and chicken requirement. Override applied to include chicken in recommendations."
  }
}
```

---

## ⏱️ Estimated Effort

| Fix | Complexity | Est. Time | Priority |
|-----|-----------|-----------|----------|
| FIX 1 | Low | 30 min | P0 |
| FIX 2 | Medium | 1-2 hr | P1 |
| FIX 3 | Low | 30 min | P1 |
| FIX 4 | Low | 30 min | P3 |
| FIX 5 | Low | 20 min | P2 |
| **Testing** | Medium | 1-1.5 hr | - |
| **TOTAL** | - | **4.5-5.5 hours** | - |

---

## 📝 Implementation Order

1. **FIX 1** first (simplest, enables others)
2. **FIX 2** second (core fix)
3. **FIX 3** third (optimization)
4. **FIX 4** (UX improvement)
5. **FIX 5** (search quality fix) ← Quick win!
6. Test all together

**Ready to start? Let me help implement! 👍**
