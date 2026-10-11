# Personalization and Runner Adaptation

## Overview

The personalization loop is:

```text
authenticated user
  -> existing route recommendations
  -> generic difficulty
  -> personalized difficulty
  -> target-difficulty reranking
  -> completed run
  -> perceived feedback
  -> future predictions adapt
```

Personalization is layered around the existing environmental and recommendation pipeline. It does not replace feasibility or environmental filtering.

## Accounts and identity

Accounts are stored in `data/runtime/accounts.sqlite3`. Registration normalizes usernames case-insensitively, assigns an immutable UUID user ID, hashes passwords with scrypt, and creates a server-side session. Sessions are presented through an HttpOnly `outdoorwise_session` cookie. Logout deletes the server-side session and clears the cookie.

Account identity is separate from personalization records. Authenticated user-scoped endpoints reject access to another user's UUID.

## Personalization data model

The dedicated personalization repository stores separate JSON files under `data/runtime/personalization/`:

- `completed_runs.json`: route, completion time, actual distance/duration, derived pace, and any saved prediction.
- `favourites.json`: user/route pairs and creation timestamps. Duplicate additions are idempotent.
- `difficulty_feedback.json`: linked completed run, difficulty from 1–5, optional tags/comment, and timestamp.

Completed runs, favourites, and feedback are user-isolated. They do not reuse environmental pipeline run JSON files.

## Running profile

`derive_running_profile` computes a profile from history rather than persisting a separate profile document. It includes:

- total, mean, median, recent, and interquartile-style typical distances;
- mean and median pace;
- comfortable distance from runs rated 2 or 3;
- mean/median perceived difficulty;
- recent difficulty trend;
- usable run count and `none`/`low`/`medium`/`high` confidence.

Favourites contribute only to the displayed favourite count. They are not used for difficulty prediction.

## Generic difficulty

`GenericDifficultyEstimator` returns an application effort estimate from 1–5, not a medical diagnosis. Its independent components include route distance and rainfall. Heat uses a non-double-counting hierarchy:

1. WBGT component when WBGT is available;
2. official heat-stress category when WBGT is unavailable;
3. temperature and humidity fallback components when neither is available.

The result is bounded to 1–5 and includes component explanations. Missing values are handled as unavailable rather than silently converted to zero.

## Personalized difficulty

`PersonalizedDifficultyPredictor` uses only prior completed runs with linked feedback. For each usable prior run:

```text
residual = actual difficulty - generic predicted difficulty
```

The implementation uses the most recent ten residuals:

```text
historical_bias = median of up to 10 recent usable residuals
shrinkage_weight = n / (n + 3)
bias_adjustment = shrinkage_weight * historical_bias

distance_ratio = (route_distance - comfortable_distance)
                 / comfortable_distance
distance_adjustment = 0.5 * clamp(distance_ratio, -0.5, 1.0)
                      * shrinkage_weight

personalized_difficulty = clamp(
    generic_difficulty + bias_adjustment + distance_adjustment,
    1,
    5
)
```

With no usable feedback, `n=0`, shrinkage is zero, and the personalized prediction equals the generic estimate. Feedback from the current run is not available while that run is being predicted. The predictor reports confidence, history count, adjustments, and reasons.

## Difficulty-aware reranking

The existing recommender first generates the authoritative feasible candidate set. The personalization layer does not reintroduce environmentally unsuitable routes or change recommendation scoring.

For each approved candidate:

```text
difficulty_mismatch = abs(personalized_difficulty - target_difficulty)
```

Candidates are sorted by:

```text
(difficulty_mismatch ASC, original_rank ASC)
```

The target is request-specific and is not stored in the user profile. **Overall recommendation rank** is the rank from the existing recommender before matching. **Your difficulty-match rank** is the personalization order after the two-stage sort. Cold-start users still rank using generic difficulty, with an explanation that more history is needed.

## GPX export

`GET /api/routes/{route_id}/export.gpx` reads the existing route GeoJSON geometry and writes a GPX 1.1 track. GeoJSON `[longitude, latitude]` coordinates become GPX `lon` and `lat` attributes in the original order. No route is generated or altered, and elevation and per-point timestamps are not invented.

## Evaluation

`outdoorwise.evaluation.personalization` performs chronological replay. An observation is eligible when it has linked feedback, a generic prediction, and a valid completion timestamp. Personalised prediction is replayed using only runs strictly earlier than the evaluated run, preventing future-feedback leakage.

The output includes:

- observation and user counts;
- generic and personalized MAE and RMSE;
- exact rounded accuracy and within-one accuracy;
- mean signed error and absolute/percentage improvement;
- learning buckets: 0, 1–2, 3–5, and 6+ prior runs;
- per-user metrics and raw prediction rows;
- comparison, learning, scatter, and per-user figures.

Real production history is the default:

```bash
python -m outdoorwise.evaluation.personalization
```

Synthetic data requires an explicit flag and is written under `data/runtime/evaluation/synthetic/`, never under account or personalization history:

```bash
python -m outdoorwise.evaluation.personalization --synthetic
```

Synthetic results must be labelled synthetic and are not evidence of real-user performance. A real pilot workflow is: register/login, complete a route, retain the generic/personalized prediction, submit perceived difficulty, repeat, then run the real-data command.

## API endpoints

### Accounts

- `GET /api/auth/username-availability?username=...`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

### Runs, favourites, and feedback

- `POST /api/users/{user_id}/runs`
- `GET /api/users/{user_id}/runs`
- `GET /api/users/{user_id}/runs/{completed_run_id}`
- `PUT /api/users/{user_id}/favourites/{route_id}`
- `DELETE /api/users/{user_id}/favourites/{route_id}`
- `GET /api/users/{user_id}/favourites`
- `POST /api/users/{user_id}/runs/{completed_run_id}/feedback`
- `GET /api/users/{user_id}/feedback`

### Profile, difficulty, and recommendations

- `GET /api/me/running-profile`
- `GET /api/me/routes/{route_id}/personalized-difficulty`
- `POST /api/me/recommendations` with `target_difficulty` and existing recommendation preferences
- `GET /api/routes/{route_id}/difficulty`
- `GET /api/routes/{route_id}/export.gpx`

Anonymous users continue to use the existing generic recommendation endpoint. The personalized recommendation endpoint requires the authenticated session.
