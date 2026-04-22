# LLM Service - Dich vu goi Model ngon ngu lon

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/ollama_nutrition_service.py`, `app/services/llm_service_fully.py`

---

## Tong quan

He thong Gym Food RAG su dung **hai LLM service rieng biet** phuc vu hai nhom chuc nang khac nhau:

| Service | File | Muc dich chinh |
|---------|------|----------------|
| `OllamaNutritionService` | `ollama_nutrition_service.py` | Sinh JSON dinh duong (phan tich thuc pham, tinh macro) |
| `LLMService` | `llm_service_fully.py` | Giao dien thong nhat cho chat, Q&A, embedding legacy |

Ca hai deu doc bien moi truong `LLM_BACKEND` de quyet dinh backend nao duoc su dung.

---

## 1. OllamaNutritionService

### 1.1 Khoi tao va chon backend

Khi khoi tao, class doc `settings.LLM_BACKEND` va chuyen sang mot trong hai che do:

- **`ollama`** (mac dinh): Ket noi toi Ollama server qua HTTP REST.
  - URL: `settings.OLLAMA_BASE_URL`
  - Model: `settings.OLLAMA_MODEL`
- **`gemini`** (hoac `google`): Su dung Google Gemini API qua `genai.Client`.
  - Model: `settings.GEMINI_MODEL`
  - API key: `settings.GOOGLE_API_KEY` hoac bien moi truong `GOOGLE_API_KEY`

**Fallback tu dong:** Neu `LLM_BACKEND` la `gemini` nhung khong tim thay `GOOGLE_API_KEY`, service tu dong chuyen ve Ollama. Tuong tu, neu gia tri `LLM_BACKEND` khong hop le (khac `ollama`/`gemini`/`google`), he thong cung fallback ve Ollama.

### 1.2 generate_text(prompt, temperature=0.2)

Ham chinh de sinh van ban tu LLM. Tra ve chuoi `str` (raw text).

**Khi backend la Ollama:**

```
POST {OLLAMA_BASE_URL}/api/generate
```

Payload: model, prompt, `stream=False`, `format="json"`, `temperature=0.2`, `num_ctx=8192`.
Timeout cau hinh qua `settings.OLLAMA_REQUEST_TIMEOUT_SECONDS`. Raise `RuntimeError` neu timeout.

**Khi backend la Gemini:**

Su dung `self.client.models.generate_content()` voi `temperature` tu tham so,
`response_mime_type="application/json"`, `max_output_tokens=8192`.
Raise `ValueError` neu `response.text` rong.

### 1.3 parse_json(raw_text)

Chuyen doi van ban raw tu LLM thanh Python `dict`.

**Logic xu ly:**

1. Loai bo markdown code fences (``` ... ```) neu co.
2. Thu `json.loads()` tren toan bo text.
3. Neu that bai, tim cap `{` dau tien va `}` cuoi cung, cat ra snippet roi parse lai.
4. Neu van that bai, raise `ValueError` voi thong bao loi cu the.

Dieu nay dam bao LLM co the tra ve JSON duoc boc trong markdown hoac co text thua ma van parse duoc.

### 1.4 Singleton instance

```python
ollama_nutrition_service = OllamaNutritionService()
```

Module-level singleton. Import truc tiep tu bat ky dau:
```python
from app.services.ollama_nutrition_service import ollama_nutrition_service
```

---

## 2. LLMService (Unified Interface)

### 2.1 Khoi tao da backend

`LLMService` ho tro **ba backend** thay vi hai:

| Backend | Bien moi truong | Mo ta |
|---------|-----------------|-------|
| `ollama` | `LLM_BACKEND=ollama` | Local model qua REST API |
| `gemini` | `LLM_BACKEND=gemini` | Google Gemini API |
| `openai` | `LLM_BACKEND=openai` | OpenAI ChatCompletion API |

Khi khoi tao:

- **Gemini client** luon duoc load (de phuc vu embedding legacy hoac backup), bat ke backend chinh la gi.
  - Model: `gemini-2.5-flash`
  - Embedding model: `models/text-embedding-004`
- **Ollama** cau hinh qua `OLLAMA_BASE_URL` (mac dinh `http://localhost:11434`) va `OLLAMA_MODEL` (mac dinh `qwen2.5:3b`).
- **OpenAI** chi khoi tao khi `LLM_BACKEND=openai` va co `OPENAI_API_KEY`. Model mac dinh: `gpt-3.5-turbo`.

### 2.2 generate_answer(prompt) - API V2

Ham don gian nhan mot prompt day du (da bao gom context) va tra ve text.

```python
def generate_answer(self, prompt: str) -> str
```

Routing logic:
- `ollama` -> `_call_ollama(prompt)`
- `openai` -> `_call_openai(prompt)`
- Mac dinh (bao gom `gemini`) -> `_call_gemini(prompt)`

### 2.3 generate_response(system_prompt, user_question, context) - API V1 Legacy

Ham cu nhan ba tham so rieng le, ghep lai thanh mot prompt lon roi goi `generate_answer()`.

```python
def generate_response(self, system_prompt: str, user_question: str, context: str) -> str
```

Template noi bo:
```
{system_prompt}

CONTEXT INFORMATION:
{context}

USER QUESTION:
{user_question}
```

### 2.4 get_embedding(text) - Embedding Legacy

Luon su dung **Gemini client** (khong phu thuoc backend chinh) de tao embedding vector.

```python
def get_embedding(self, text: str) -> list
```

- Model: `models/text-embedding-004`
- Xu ly: Thay `\n` bang khoang trang truoc khi gui.
- Tra ve `list` rong neu khong co Gemini client hoac loi xay ra.

### 2.5 Internal workers

#### _call_ollama(prompt)

```
POST {OLLAMA_BASE_URL}/api/generate
```

| Thong so | Gia tri |
|----------|---------|
| `temperature` | `0.3` |
| `num_ctx` | `4096` |
| `stream` | `False` |
| `timeout` | `60` giay |

Raise exception neu status code khac 200.

#### _call_gemini(prompt)

Su dung `self.gemini_client.models.generate_content()`. Kiem tra safety filter - neu `response.text` rong thi raise `ValueError`. Loi duoc re-raise de controller xu ly.

#### _call_openai(prompt)

Su dung `openai.ChatCompletion` voi:
- System prompt co dinh: "Ban la tro ly AI tuan thu tuyet doi cac huong dan trong prompt cua nguoi dung."
- Temperature: `0.5`
- Tra ve `response.choices[0].message.content`

### 2.6 Singleton pattern

```python
_llm_instance = None

def get_llm_service():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService()
    return _llm_instance

llm_service = get_llm_service()
```

Co hai cach su dung:
- Import truc tiep: `from app.services.llm_service_fully import llm_service`
- Goi ham factory: `from app.services.llm_service_fully import get_llm_service`

---

## 3. Cau hinh bien moi truong

| Bien | Mac dinh | Mo ta |
|------|----------|-------|
| `LLM_BACKEND` | `ollama` | Chon backend: `ollama`, `gemini`, `google`, `openai` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL cua Ollama server |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model Ollama su dung |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | (tu config) | Thoi gian timeout cho Ollama |
| `GOOGLE_API_KEY` | (bat buoc cho Gemini) | API key cua Google AI |
| `GEMINI_MODEL` | (tu config) | Model Gemini cho OllamaNutritionService |
| `OPENAI_API_KEY` | (bat buoc cho OpenAI) | API key cua OpenAI |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | Model OpenAI su dung |

---

## 4. So sanh hai service

| Tieu chi | OllamaNutritionService | LLMService |
|----------|------------------------|------------|
| Backend ho tro | Ollama, Gemini | Ollama, Gemini, OpenAI |
| JSON mode | Co (Ollama `format: json`, Gemini `response_mime_type`) | Khong (tra raw text) |
| parse_json() | Co | Khong |
| Embedding | Khong | Co (Gemini legacy) |
| Temperature mac dinh | 0.2 | 0.3 (Ollama), 0.5 (OpenAI) |
| Context window | 8192 | 4096 (Ollama) |
| Su dung chinh | Pipeline dinh duong V3 | Chat Q&A V1/V2 |
| Error handling | Chi tiet (log tung loai loi) | Don gian (re-raise) |

---

## 5. Luu y khi deploy

- Trong Docker, `OLLAMA_BASE_URL` thuong la `http://ollama:11434` (ten container).
- Gemini fallback tu dong khi API key thieu (khong crash).
- Ca hai service dung singleton pattern - chi mot instance trong toan bo vong doi ung dung.

---

## Tai lieu lien quan

- [Tong quan kien truc](../architecture/overview.md)
- [RAG Pipeline](../architecture/rag-pipeline.md)
- [Cau hinh he thong](../getting-started/configuration.md)
- [Cache va State Management](./cache-state.md)
- [Evaluation Service](./evaluation-service.md)
