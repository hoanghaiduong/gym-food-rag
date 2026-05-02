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
