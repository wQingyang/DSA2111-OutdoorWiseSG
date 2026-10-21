# Shared Synthetic Test Runners

These accounts are synthetic demo accounts for demonstrating the
personalized recommendation system.

## test_runner_1

Username: `test_runner_1`  
Password: `Password123`

Profile:

- shorter-distance / slightly slower runner
- generally reports higher perceived difficulty

## test_runner_2

Username: `test_runner_2`  
Password: `Password123`

Profile:

- can run longer distances
- runs somewhat faster
- generally reports lower perceived difficulty

Use these accounts to compare:

- Generic difficulty
- Predicted difficulty for you
- Difficulty difference
- Shared rank
- Your difficulty-match rank

These are demo-only credentials. Do not reuse `Password123` for a real
account.

The committed SQLite database intentionally contains the two synthetic users,
but no active sessions. Their existing completed-run histories and difficulty
feedback are preserved as synthetic demonstration data.

Current/demo environmental runtime files are not shared and are regenerated
automatically by the application.

## If you already have local runtime files

Before pulling the shared runtime snapshot, back up any local runtime data
you want to keep. Git may refuse to overwrite an existing untracked or
ignored file at the same path.

For example:

```sh
mv data/runtime data/runtime_backup
```

Then pull the shared snapshot:

```sh
git pull origin main
```

Start normally in demo mode:

```sh
OUTDOORWISE_DATA_MODE=demo \
python -m uvicorn outdoorwise.api.app:app \
  --host 127.0.0.1 \
  --port 8000
```
