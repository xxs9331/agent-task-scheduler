# Skill evals

`global_scheduler_skill_cases.jsonl` records positive and negative trigger
examples. Infrastructure tests validate that every case is parseable and that
the plugin manifest resolves its Skill directory. Behavioral evaluation by a
model harness can consume the same JSONL without changing the Skill package.
