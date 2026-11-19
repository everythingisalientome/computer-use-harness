"""The model client and the action format (build piece 2).

The modules, one job each:

- connection.py  reads config/model-connection.yaml and turns a slot name into a model
- prompts.py     builds the messages for the four kinds of call: act, verify, read, judgment
- answers.py     checks a model's answer against docs/action-format.md (no network)
- client.py      sends a call, re-asks once on a bad answer, refuses to send a secret

Nothing here touches the screen. The step loop (piece 3) joins this package to
harness/screen.
"""
