# Kế Hoạch Nâng Cấp Toàn Diện Để Chạy Production

## Tóm tắt
- Mục tiêu chốt là theo 2 phase: Phase A khóa `ready_for_pilot` end-to-end cho `intent + retrieval + recommendation + judge`, Phase B mới tối ưu tiếp các metric chẩn đoán để tiến sát mức tốt nhất có thể trong giới hạn metric hiện tại.
- Trạng thái hiện tại của repo: retrieval production KPI đã đạt nền tốt với `case_count=304`, `equivalence_recall_at_20=1.0`, `required_tag_hit_rate=0.992325`, toàn bộ safety count bằng `0`; nhưng canonical root vẫn thiếu `intent_dataset_evaluation.json`, `intent_classification_report.json`, và `summary.json`, nên chưa thể judge production đầy đủ.
- Nợ chính của retrieval hiện không còn là safety/family recall mà là completeness và chất lượng top đầu: `exact_id_recall_at_20=0.871711`, `precision_at_4=0.441612`, và benchmark full mới có `304` thay vì `306` case.
- Định nghĩa “100%” cho đợt này là: pass toàn bộ `production_kpi` của judge hiện tại; sau đó mới đẩy `diagnostic_kpi` lên mức tối đa thực tế, không theo kiểu ép mọi scalar về `1.0`.

## Thay đổi triển khai
### Phase A: Khóa pass production end-to-end
- Giữ nguyên collection/alias retrieval đang pass làm baseline; không reindex hay đổi policy KB nữa trong Phase A trừ khi recommendation suite lộ ra safety regression mới.
- Chuẩn hóa lại canonical artifact root để judge luôn đọc đúng bộ chuẩn: root chỉ chứa bộ canonical cố định, còn mọi slice/debug/per-case artifact tiếp tục nằm dưới `_debug`.
- Regenerate canonical intent bằng `scripts/evaluate_intent_dataset.py` ở mode mặc định, để tạo lại `intent_dataset_evaluation.json` và `intent_classification_report.json` trong root.
- Chạy recommendation suite theo hai bước cố định: debug full run có case files để lộ lỗi thật, sau đó canonical full run chỉ ghi `summary.json`. Không promote debug artifact vào root nếu canonical full chưa pass.
- Giữ contract recommendation thật chặt: model chỉ được tổng hợp từ candidate đã qua validation; mọi item render cho UI phải đi qua `safe_display_name`; mọi candidate có `final_output_allowed=false` bị block trước khi ra output; không cho model tự bịa thêm món ngoài pool an toàn.
- Dùng `scripts/judge_production_readiness.py` làm release gate duy nhất. `judge_cutover.py` chỉ dùng phụ khi cần đào sâu case-level debug, không được coi là hard dependency của canonical run.
- Thêm preflight check cho pipeline release: nếu thiếu bất kỳ canonical file bắt buộc nào thì fail sớm trước khi chạy judge, thay vì để người chạy tự đoán.

### Phase B: Nâng chất lượng retrieval và benchmark sau khi đã pass
- Sửa benchmark generator để khôi phục full retrieval suite từ `304` về `306` case, và thêm assertion cứng: full run không được silently rơi case; nếu thiếu case thì phải fail với danh sách `dropped_case_ids`.
- Tách benchmark positive nội bộ thành hai lớp rõ ràng:
  - `equivalence_positive_entity_ids` cho family/equivalence gate.
  - `exact_anchor_entity_ids` cho exact-id diagnostics.
- Giữ nguyên threshold production hiện tại; việc tách benchmark chỉ nhằm bỏ các hình phạt exact-id không phản ánh đúng mục tiêu production, không phải để nới chuẩn.
- Siết ranking top đầu trong retrieval runtime theo hướng `availability-aware + family-strict`: anchor mạnh đi trước, giới hạn sibling cùng family ở top-4/top-10, giữ role diversity vừa đủ, và không để support items lấn chỗ main family.
- Dùng Phase B để kéo các metric diagnostic lên ngưỡng thực dụng:
  - `exact_id_recall_at_20 >= 0.90`
  - `exact_id_mrr_at_20 >= 0.82`
  - `precision_at_4 >= 0.60`
  - giữ `equivalence_recall_at_20 = 1.0` và toàn bộ safety count = `0`
- Canonical retrieval eval tiếp tục chạy deterministic; không bật LLM query rewrite trong gate run. LLM chỉ được phép ở tầng generation và vẫn bị ràng buộc bởi validated candidate set.

### Vận hành và CI
- Chuẩn hóa một luồng chạy pre-prod duy nhất cho team: `intent -> retrieval lint -> retrieval eval -> recommendation debug -> recommendation canonical -> judge`.
- Sau mỗi run pass, chỉ promote/cập nhật canonical artifact của pipeline vừa pass; sau đó prune debug run cũ để `_debug` chỉ giữ run mới nhất có giá trị và run đang điều tra.
- Thêm regression checks trong CI:
  - canonical root không chứa file ngoài whitelist.
  - retrieval production KPI không được tụt khỏi bộ pass hiện tại.
  - recommendation canonical run phải sinh đúng `summary.json` và không phụ thuộc vào per-case JSON.
  - `production_scorecard.json` phải có verdict `ready_for_pilot` trước khi coi là sẵn sàng release.

## Interface và contract cần giữ/chỉnh
- Không đổi public API người dùng trong đợt này.
- Contract canonical artifact giữ nguyên: root chỉ có các file chuẩn mà judge đang đọc; case-level JSON và debug detail chỉ sống trong `_debug`.
- Internal benchmark schema của retrieval sẽ thêm `equivalence_positive_entity_ids` và `exact_anchor_entity_ids`; đây là thay đổi nội bộ cho bench/scoring, không ảnh hưởng API runtime.
- `summary.json` tiếp tục là nguồn sự thật duy nhất cho recommendation judge; không thêm hard dependency mới vào per-case files.

## Test plan và acceptance
- Chạy lại canonical intent:
  - `.\myenv\Scripts\python -X utf8 scripts\evaluate_intent_dataset.py`
- Chạy canonical retrieval:
  - `.\myenv\Scripts\python -X utf8 scripts\lint_retrieval_dataset.py`
  - `.\myenv\Scripts\python -X utf8 scripts\evaluate_retrieval_dataset.py`
- Chạy recommendation debug trước để bóc lỗi:
  - `.\myenv\Scripts\python -X utf8 scripts\test_nutrition_cases.py --artifact-mode debug --run-name preprod_full --emit-case-files`
- Khi debug full pass theo target, chạy canonical recommendation:
  - `.\myenv\Scripts\python -X utf8 scripts\test_nutrition_cases.py`
- Chạy judge cuối:
  - `.\myenv\Scripts\python -X utf8 scripts\judge_production_readiness.py`
- Acceptance của Phase A:
  - Canonical root có đủ `intent_dataset_evaluation.json`, `intent_classification_report.json`, `retrieval_dataset_evaluation.json`, `retrieval_classification_report.json`, `retrieval_dataset_lint.json`, `summary.json`, `production_scorecard.json`.
  - Verdict trong `production_scorecard.json` là `ready_for_pilot`.
  - Intent pass toàn bộ production_kpi hiện tại.
  - Retrieval giữ `equivalence_recall_at_20 >= 0.98`, `required_tag_hit_rate >= 0.98`, và toàn bộ safety count bằng `0`.
  - Recommendation đạt `case_count >= 50`, `validation_pass_rate >= 0.95`, `meal_realism_pass_rate >= 0.95`, `main_meal_anchor_pass_rate = 1.0`, `allergy_violation_rate = 0`, `diet_violation_rate = 0`, `unsafe_raw_output_count = 0`, `unsafe_label_count = 0`.
- Acceptance của Phase B:
  - Full retrieval benchmark trở lại `306` case.
  - `exact_id_recall_at_20 >= 0.90`
  - `precision_at_4 >= 0.60`
  - Không có regression ở family recall hoặc safety.

## Giả định và mặc định chốt
- Mọi lệnh benchmark/judge dùng `.\myenv\Scripts\python -X utf8`; không dùng `python` thường để tránh lệch environment và false failure.
- “Pass production” được hiểu là pass `production_kpi` của `judge_production_readiness.py`; `diagnostic_kpi` là mục tiêu tối ưu của Phase B chứ không phải blocker của Phase A.
- Backend API, token hoặc cặp `username/password`, và alias Qdrant đang active đều sẵn sàng khi chạy recommendation suite.
- Cho phép chỉnh benchmark/schema nội bộ nếu và chỉ nếu không hạ threshold production, không nới safety policy, và không che giấu regression thật của runtime.
