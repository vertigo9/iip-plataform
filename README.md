# D-OBSIDIAN-06.7 — Restore Release Checkpoint

The cleanup verification exposed a real regression caused by the cleanup:
`POST95_RELEASE_CHECKPOINT.json` was moved out of the repository root, but an
existing certified compatibility test still expects that file at root.

Evidence:
- full regression: 844 passed / 2 failed / 5 skipped;
- both failures trace to `test_release_checkpoint_json_matches_baseline`;
- the missing path is exactly `POST95_RELEASE_CHECKPOINT.json`.

This package restores ONLY that compatibility artifact from the cleanup
manifest. It does not roll back the rest of the cleanup.

Run:

cd D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1

powershell -ExecutionPolicy Bypass -File .\RESTORE_0674_RELEASE_CHECKPOINT.ps1

powershell -ExecutionPolicy Bypass -File .\RUN_0674_RELEASE_CHECKPOINT_RESTORE_VERIFY.ps1

After the focused + integrated checks pass, we can run the full regression
once, then decide whether the checkpoint should remain at root permanently or
be migrated via a controlled test/configuration update.
