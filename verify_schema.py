#!/usr/bin/env python3
"""
Quick verification checklist for nutrition_food_v1 schema.
7-point pass/fail check on foods_full_profile.jsonl.
"""

import json
import math
import sys

JSONL_FILE = "foods_full_profile.jsonl"

def verify_schema():
    records = []
    errors = {
        "nan_in_json": [],
        "entity_id_dup": set(),
        "entity_id_unique_pass": True,
        "entity_type_mismatch": [],
        "portion_basis_mismatch": [],
        "kcal_calc_missing": [],
        "updated_at_format": [],
        "content_empty": [],
    }

    entity_ids = {}

    try:
        with open(JSONL_FILE, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                rec = json.loads(line.strip())
                records.append(rec)

                # 1. Check for NaN in JSON
                rec_str = json.dumps(rec)
                if "NaN" in rec_str:
                    errors["nan_in_json"].append(line_no)

                # 2. Check entity_id uniqueness
                eid = rec.get("entity_id")
                if eid:
                    if eid in entity_ids:
                        errors["entity_id_dup"].add(eid)
                        errors["entity_id_unique_pass"] = False
                    else:
                        entity_ids[eid] = line_no

                # 3. Check entity_type
                if rec.get("entity_type") != "food":
                    errors["entity_type_mismatch"].append(
                        (line_no, rec.get("entity_type"))
                    )

                # 4. Check portion_basis
                if rec.get("portion_basis") != "per_100g":
                    errors["portion_basis_mismatch"].append(
                        (line_no, rec.get("portion_basis"))
                    )

                # 5. Check kcal calculation fields
                if rec.get("calculated_kcal_from_macros") is None:
                    errors["kcal_calc_missing"].append(
                        (line_no, "calculated_kcal_from_macros missing")
                    )
                if "kcal_gap_pct" not in rec:
                    errors["kcal_calc_missing"].append(
                        (line_no, "kcal_gap_pct missing")
                    )

                # 6. Check updated_at format (ISO-8601 UTC)
                updated_at = rec.get("updated_at")
                if not isinstance(updated_at, str):
                    errors["updated_at_format"].append(
                        (line_no, f"not string: {type(updated_at)}")
                    )
                elif not (
                    updated_at.endswith("Z")
                    or "+00:00" in updated_at
                ):
                    errors["updated_at_format"].append(
                        (line_no, f"bad format: {updated_at}")
                    )

                # 7. Check content not empty
                content = rec.get("content")
                if not content or len(str(content).strip()) == 0:
                    errors["content_empty"].append(line_no)

    except FileNotFoundError:
        print(f"ERROR: {JSONL_FILE} not found")
        return False
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON at line: {e}")
        return False

    # Report
    print("=" * 70)
    print("SCHEMA VERIFICATION: nutrition_food_v1")
    print("=" * 70)
    print(f"Total records: {len(records)}")
    print()

    results = []

    # 1. No NaN in JSON
    passed = len(errors["nan_in_json"]) == 0
    results.append(("✓" if passed else "✗", "No NaN in JSON", passed))
    if not passed:
        print(f"  FAIL: Found NaN at lines: {errors['nan_in_json'][:5]}...")

    # 2. entity_id unique
    passed = errors["entity_id_unique_pass"]
    results.append(("✓" if passed else "✗", "entity_id unique", passed))
    if not passed:
        print(f"  FAIL: Duplicates: {list(errors['entity_id_dup'])[:5]}")

    # 3. entity_type = food
    passed = len(errors["entity_type_mismatch"]) == 0
    results.append(("✓" if passed else "✗", "entity_type = food", passed))
    if not passed:
        print(f"  FAIL: Mismatches at lines: {errors['entity_type_mismatch'][:5]}")

    # 4. portion_basis = per_100g
    passed = len(errors["portion_basis_mismatch"]) == 0
    results.append(("✓" if passed else "✗", "portion_basis = per_100g", passed))
    if not passed:
        print(
            f"  FAIL: Mismatches at lines: {errors['portion_basis_mismatch'][:5]}"
        )

    # 5. kcal fields present and calculated
    passed = len(errors["kcal_calc_missing"]) == 0
    results.append(
        ("✓" if passed else "✗", "kcal calc fields present", passed)
    )
    if not passed:
        print(f"  FAIL: Missing at lines: {errors['kcal_calc_missing'][:5]}")

    # 6. updated_at ISO-8601 UTC
    passed = len(errors["updated_at_format"]) == 0
    results.append(("✓" if passed else "✗", "updated_at ISO-8601 UTC", passed))
    if not passed:
        print(f"  FAIL: Bad format at lines: {errors['updated_at_format'][:5]}")

    # 7. content not empty
    passed = len(errors["content_empty"]) == 0
    results.append(("✓" if passed else "✗", "content not empty", passed))
    if not passed:
        print(f"  FAIL: Empty at lines: {errors['content_empty'][:5]}")

    print()
    print("Checklist:")
    for symbol, check, passed in results:
        print(f"  {symbol} {check}")

    all_passed = all(p for _, _, p in results)
    print()
    print("=" * 70)
    if all_passed:
        print("✓ ALL CHECKS PASSED - Schema v1 ready for vector upsert")
        return True
    else:
        print("✗ SOME CHECKS FAILED - Please review above")
        return False

if __name__ == "__main__":
    ok = verify_schema()
    sys.exit(0 if ok else 1)
