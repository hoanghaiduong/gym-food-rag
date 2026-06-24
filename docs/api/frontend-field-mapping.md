# Frontend Field Mapping

> Updated: 2026-04-30
> Source of truth: `docs/api/openapi.json`

## Principle

Backend public API keeps `snake_case` to match the current FastAPI/Pydantic contract.
Frontend may keep UI/domain models in `camelCase`, but should map at the API adapter boundary.

## Auth Tokens

| Backend field | Frontend field | Note |
| --- | --- | --- |
| `access_token` | `accessToken` | Send as `Authorization: Bearer <accessToken>`. |
| `refresh_token` | `refreshToken` | Store securely and rotate after every refresh. |
| `token_type` | `tokenType` | Usually `bearer`. |
| `permissions` | `permissions` | Use for feature gating. |

Refresh flow:

1. If an authenticated API returns `401`, call `POST /api/v3/auth/refresh` once.
2. Replace both `accessToken` and `refreshToken` from the response.
3. Retry the original request once.
4. If refresh fails, clear local tokens and send the user to login.

## Register / Current User

| Frontend field | Backend field |
| --- | --- |
| `fullName` | `full_name` |
| `email` | `email` |
| `password` | `password` |
| `phone` | `phone` |
| `referralCode` | `referral_code` |
| `avatarUrl` | `avatar_url` |

## Profile / Onboarding

`GET /api/v3/auth/me` returns `data.is_profile_completed` explicitly so the app
can decide whether to show onboarding without reimplementing backend completion
rules. The fallback fields are `target_goal`, `goal_normalized_internal`,
`planning_strategy`, `age`, `gender`, `height`, `weight`, and `activity_level`.

| Frontend field | Backend field | Backend normalized value |
| --- | --- | --- |
| `heightCm` | `height` | number in cm |
| `weightKg` | `weight` | number in kg |
| `goal` | `target_goal` | `gain_muscle`, `lose_weight`, `maintain` |
| `activityLevel` | `activity_level` | `sedentary`, `light`, `moderate`, `active`, `very_active` |
| `workoutsPerWeek` | `workouts_per_week` | integer |
| `workoutMinutes` | `workout_minutes` | integer |
| `trainingTypes` | `training_types` | comma-separated string in backend response |
| `dietStyle` | `dietary_preference` | `omnivore`, `vegetarian`, `vegan`, `pescatarian` |
| `allergies` | `allergies` | comma-separated normalized allergy tags |
| `dislikedFoods` | `disliked_foods` | comma-separated string |
| `favoriteMeals` | `favorite_meals` | comma-separated string |
| `avoidMeals` | `avoid_meals` | comma-separated string |
| `medicalConditions` | `medical_conditions` | comma-separated string |

Recommended frontend values from `GET /api/v3/nutrition/options`:

| Frontend value | Send to backend |
| --- | --- |
| `gain-muscle` | `target_goal` accepts it and normalizes to `gain_muscle` |
| `lose-fat` | `target_goal` accepts it and normalizes to `lose_weight` |
| `balanced` | `dietary_preference` accepts it and normalizes to `omnivore` |
| `keto` / `paleo` | currently normalized to `omnivore` until dedicated diet logic is implemented |

## Recommendation Request

| Frontend field | Backend field |
| --- | --- |
| `instruction` | `instruction` |
| `mealCount` | `meal_count` |
| `topK` | `top_k` |
| `maxRevisionRounds` | `max_revision_rounds` |
| `useCache` | `use_cache` |
| `includeDebug` | `include_debug` |
| `dislikedFoods + avoidMeals` | `excluded_foods` |
| `favoriteMeals` | `must_include` or append to `instruction` |

For `/api/v3/nutrition/recommendation-agent`, if `data.status === "needs_clarification"`,
render `data.answer` as the next question and do not render a meal plan because
`data.recommendation` is `null`.

## Dashboard Overview

Primary endpoint: `GET /api/v3/dashboard/overview`

During rollout, frontend may fall back to `GET /api/v3/nutrition/profile` if
the dashboard endpoint returns `404`.

| Frontend field | Backend field |
| --- | --- |
| `greetingName` | `greeting_name` |
| `goalLabel` | `goal_label` |
| `weeklyProgress` | `weekly_progress` |
| `caloriesConsumed` | `calories_consumed` |
| `caloriesTarget` | `calories_target` |
| `caloriesRemaining` | `calories_remaining` |
| `bmi` | `bmi` |
| `weightKg` | `weight_kg` |
| `bmr` | `bmr` |
| `trendPoints` | `trend_points` |
| `recentPlans` | `recent_plans` |
| `profileCompleted` | `profile_completed` |

Backend `macros` is a numeric object:

```json
{"protein_g": 130, "carbs_g": 220, "fat_g": 60}
```

Frontend maps it to display rows:

```ts
[
  { label: "PRO", consumed: 0, target: proteinG, accent: "primary" },
  { label: "CARB", consumed: 0, target: carbsG, accent: "warning" },
  { label: "FAT", consumed: 0, target: fatG, accent: "info" }
]
```

## Plans / Calendar

Weekly endpoint: `GET /api/v3/plans/weekly?week_start=2026-05-04`

| Frontend field | Backend field |
| --- | --- |
| `id` | `id` |
| `dayLabel` | `day_label` |
| `title` | `title` |
| `subtitle` | `subtitle` |
| `status` | `status` (`completed`, `active`, `upcoming`, `insight`) |

Monthly endpoint: `GET /api/v3/plans/monthly?year=2026&month=5`

| Frontend field | Backend field |
| --- | --- |
| `days[].day` | `days[].day` |
| `days[].hasCompletedWorkout` | `days[].has_completed_workout` |
| `days[].hasPlannedWorkout` | `days[].has_planned_workout` |
| `days[].isToday` | `days[].is_today` |
| `monthlyProgress.workoutCompleted` | `monthly_progress.workout_completed` |
| `monthlyProgress.workoutTarget` | `monthly_progress.workout_target` |
| `monthlyProgress.nutritionCompleted` | `monthly_progress.nutrition_completed` |
| `monthlyProgress.nutritionTarget` | `monthly_progress.nutrition_target` |
| `selectedDay.date` | `selected_day.date` |
| `selectedDay.title` | `selected_day.title` |
| `selectedDay.subtitle` | `selected_day.subtitle` |
| `selectedDay.calories` | `selected_day.calories` |

## Training Recommendation

Options endpoint: `GET /api/v3/training/options`

Recommendation endpoint: `POST /api/v3/training/recommendation`

This endpoint is deterministic and does not call the LLM. It uses the user
profile plus optional request overrides to return a safe training schedule that
can be shown next to the meal plan.

| Frontend field | Backend field |
| --- | --- |
| `goal` | `goal` (`gain_muscle`, `lose_weight`, `maintain`, `endurance`, `mobility`) |
| `experienceLevel` | `experience_level` (`beginner`, `intermediate`, `advanced`) |
| `workoutsPerWeek` | `workouts_per_week` |
| `workoutMinutes` | `workout_minutes` |
| `trainingTypes` | `training_types` |
| `equipment` | `equipment` |
| `limitations` | `limitations` |
| `includeNutritionTiming` | `include_nutrition_timing` |

Response fields to map:

| Frontend field | Backend field |
| --- | --- |
| `weeklyFrequency` | `weekly_frequency` |
| `sessionMinutes` | `session_minutes` |
| `profileSummary` | `profile_summary` |
| `safetyNotes` | `safety_notes` |
| `nutritionAlignment` | `nutrition_alignment` |
| `schedule[].dayIndex` | `schedule[].day_index` |
| `schedule[].estimatedMinutes` | `schedule[].estimated_minutes` |
| `schedule[].exercises[].durationMinutes` | `schedule[].exercises[].duration_minutes` |
| `schedule[].exercises[].restSeconds` | `schedule[].exercises[].rest_seconds` |

## Meal Logs

Endpoints:

- `POST /api/v3/meals/logs`
- `GET /api/v3/meals/logs?date_from=2026-05-01&date_to=2026-05-13`
- `GET /api/v3/meals/logs/summary?date_from=2026-05-01&date_to=2026-05-13`
- `GET|PUT|DELETE /api/v3/meals/logs/{log_id}`

| Frontend field | Backend field |
| --- | --- |
| `loggedAt` | `logged_at` |
| `mealName` | `meal_name` |
| `energyKcal` | `energy_kcal` |
| `proteinG` | `protein_g` |
| `carbsG` | `carbs_g` |
| `fatG` | `fat_g` |
| `items[].entityId` | `items[].entity_id` |
| `items[].foodId` | `items[].food_id` |
| `items[].displayName` | `items[].display_name` |

Manual meal logs are user diary data only. They must not be inserted back into
the production retrieval candidate pool.

## Workout Logs

Endpoints:

- `POST /api/v3/workouts/logs`
- `GET /api/v3/workouts/logs?date_from=2026-05-01&date_to=2026-05-13`
- `GET /api/v3/workouts/logs/summary?date_from=2026-05-01&date_to=2026-05-13`
- `GET|PUT|DELETE /api/v3/workouts/logs/{log_id}`

| Frontend field | Backend field |
| --- | --- |
| `loggedAt` | `logged_at` |
| `workoutType` | `workout_type` |
| `durationMinutes` | `duration_minutes` |
| `caloriesEstimated` | `calories_estimated` |
| `exercises[].exerciseName` | `exercises[].exercise_name` |
| `exercises[].weightKg` | `exercises[].weight_kg` |
| `exercises[].durationMinutes` | `exercises[].duration_minutes` |
| `exercises[].restSeconds` | `exercises[].rest_seconds` |

## Saved Plans

Endpoints:

- `POST /api/v3/plans/saved`
- `GET /api/v3/plans/saved?type=weekly`
- `GET|PUT|DELETE /api/v3/plans/saved/{plan_id}`
- `POST /api/v3/plans/weekly/generate`
- `POST /api/v3/plans/monthly/generate`

`GET /api/v3/plans/weekly` and `GET /api/v3/plans/monthly` now prefer a saved
snapshot for that date range. If none exists, they return the profile-based
fallback timeline.

## AI Control / Feedback

User feedback endpoint:

- `POST /api/v3/ai/feedback`

Admin-only endpoints require `system.config`:

- `GET|PUT /api/v3/admin/ai/config`
- `GET|POST /api/v3/admin/ai/prompts`
- `POST /api/v3/admin/ai/prompts/{version_id}/validate`
- `POST /api/v3/admin/ai/prompts/{version_id}/publish`
- `GET|POST /api/v3/admin/ai/rules`
- `POST /api/v3/admin/ai/rules/{version_id}/validate`
- `POST /api/v3/admin/ai/rules/{version_id}/publish`
- `GET /api/v3/admin/ai/feedback`
- `GET /api/v3/admin/ai/training-data/export`

Do not send API keys/secrets through these endpoints. Prompt/rule versions are
validated before publish and cannot override hard safety rules.

## General Chat

Endpoint: `POST /api/v3/chat`

Use this endpoint for general education/chat such as "TDEE la gi?" or "macro la gi?".
Do not use it to render meal plans.

If the response has `data.status === "use_nutrition_agent"`, call
`data.suggested_endpoint` (`/api/v3/nutrition/recommendation-agent`) with a
structured recommendation request. The chat endpoint intentionally does not
return final food items.

## OTP

| Frontend field | Backend field |
| --- | --- |
| `target` | `target` |
| `channel` | `channel` (`email` or `sms`) |
| `purpose` | `purpose` (`register` or `reset_password`) |
| `otpRequestId` | `otp_request_id` |
| `verificationToken` | `verification_token` |
| `newPassword` | `new_password` |

Dev mode may return `dev_code` so the app can complete local testing without SMTP/SMS.
Production must not show or depend on `dev_code`.

## Avatar Upload

Endpoint: `POST /api/v3/users/me/avatar`

- Request: `multipart/form-data`, field name `file`.
- Allowed MIME types: `image/jpeg`, `image/png`, `image/webp`.
- Max size: 5MB.
- Response field: `data.avatar_url`, mapped to frontend `avatarUrl`.

## Preferences / Biometric Unlock

Endpoints:

- `GET /api/v3/users/me/preferences`
- `PUT /api/v3/users/me/preferences`

| Frontend field | Backend field | Note |
| --- | --- | --- |
| `language` | `language` | `vi` or `en`. |
| `theme` | `theme` | `system`, `light`, or `dark`. |
| `pushNotifications` | `push_notifications` | UI notification preference. |
| `emailNotifications` | `email_notifications` | Email notification preference. |
| `marketingEmails` | `marketing_emails` | Marketing email opt-in. |
| `biometricUnlockEnabled` | `biometric_unlock_enabled` | UI preference only. Backend never receives biometric data. |

Biometric unlock must be implemented on the device:

1. User logs in normally and receives `refreshToken`.
2. If `biometricUnlockEnabled=true`, frontend stores the refresh token in secure storage protected by Face ID/Touch ID/Android biometric.
3. On next app open, frontend runs device biometric auth.
4. If successful, frontend reads `refreshToken`, calls `/api/v3/auth/refresh`, and replaces both tokens.
5. Backend only stores the preference flag; it does not store fingerprints, face data, or biometric templates.
