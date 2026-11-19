# Action format: the contract between the harness and the model

The harness makes four kinds of model call. Each one gets a fixed input and must return one JSON object in a fixed shape. The format is ours and does not depend on any model vendor.

Every call starts with the overall context, which holds only guidance that applies to every kind of call. The instructions for each kind of call follow it. No call ever contains a password: the harness keeps a register of secrets and refuses to send any call that contains one.

## 1. Act call

Used inside a screen step, once per action.

The model receives: the persona's guidance and the guardrails' "never" list, the app context, the step's intent with real values filled in, the step's hints, each value it may type with its name and value, the actions already taken in this step with their results, and the current screenshot. The persona's guidance and the "never" list go on act calls only.

Each line of the action history names the action and its result: `sent`, or `refused` with the reason. A typed value appears by its name only, never as the value. If the prompt grows too long, the oldest history lines are cut first, keeping the last five. Nothing else is cut: if the prompt is still too long, the harness stops and names the part that is too big.

The model returns exactly one action.

| Action | Fields | Example |
|---|---|---|
| `click` | `x`, `y`, `target` | `{"action": "click", "x": 912, "y": 54, "target": "Save button"}` |
| `double_click` | `x`, `y`, `target` | `{"action": "double_click", "x": 300, "y": 410, "target": "first Items row"}` |
| `type` | `value_ref` or `text` | `{"action": "type", "value_ref": "customer_name"}` |
| `key` | `keys` | `{"action": "key", "keys": "ctrl+s"}` |
| `scroll` | `x`, `y`, `direction`, `amount` | `{"action": "scroll", "x": 500, "y": 600, "direction": "down", "amount": 3}` |
| `drag` | `from_x`, `from_y`, `to_x`, `to_y` | `{"action": "drag", "from_x": 200, "from_y": 300, "to_x": 600, "to_y": 300}` |
| `wait` | `seconds` | `{"action": "wait", "seconds": 2}` |
| `step_done` | none | `{"action": "step_done"}` |
| `cannot_proceed` | `reason` | `{"action": "cannot_proceed", "reason": "A login page is showing."}` |

Every action may also carry `note`, a short sentence saying why. The harness logs it and never acts on it.

Rules:

- **Coordinates** are whole numbers from 0 to 1000 on both axes, measured on the screenshot that was sent. (0, 0) is the top left. The harness converts them to pixels.
- **`target`** names the thing being clicked in plain words. It is logged for the audit trail and is not used to find the element.
- **`type` with `value_ref`** names one of the step's `inputs`: a value from the work item or an earlier capture. The harness types the real value. This is the only way to type work item data.
- **`type` with `text`** is allowed only for a text that appears in double quotes in the step's intent or hints as written in the procedure (before values are filled in), or in the body of the step's app file, typed exactly as quoted. It is refused if it equals or contains any work item or capture value, even when that value is quoted somewhere. Anything a step expects the model to type literally must therefore be in double quotes.
- **`key`** uses lower-case names joined with `+`, for example `enter`, `tab`, `escape`, `ctrl+s`. The harness refuses any key on the persona's blocked list.
- **`wait`** is capped by the persona's guardrails.

What the harness does with a bad answer:

- Not valid JSON, an unknown action, a missing or extra field, a `value_ref` that is not one of the step's inputs, or `text` that is not allowed: the harness asks once more with the error. The error names the `value_ref` names the step allows. A second bad answer counts as a failed attempt. Every refused answer is logged with the kind of mistake.
- A single ```` ```json ```` fence around the object is allowed. Any other text around it is not.
- An action the guardrails refuse: the action is not performed, the refusal is logged, and the item goes to a human.

## 2. Verify call

Used after a step to check its "done when" condition. It is a fresh call: the model receives only the condition, with real values filled in, and a new screenshot. It does not see the step's actions.

```json
{"result": "true", "evidence": "The form title reads 'Acme Robotics 1118' and no 'Not Saved' label is shown."}
```

`result` is `true`, `false` or `unclear`. The harness treats `unclear` as `false`, except on resume of an irreversible step, where it sends the item to a human.

## 3. Read call

Used for each capture. The model receives the capture's question and a screenshot.

```json
{"visible": true, "value": "4,50,000.00"}
```

- If the value is not on the screen, the model returns `{"visible": false, "value": null}` and the item goes to a human.
- The model returns the text exactly as displayed. The harness converts it to the capture's type.
- A capture with `double_read` gets two separate read calls. The harness compares the converted values, and a difference sends the item to a human.
- A capture with `allowed_values` must return one of them.

## 4. Judgment call

Used for a judgment rule. The model receives the rule's question, with real values filled in, and a screenshot.

```json
{"answer": "yes", "evidence": "The Customer field shows 'Acme Robotics 1118'."}
```

`answer` is `yes`, `no` or `not_sure`. `not_sure` always sends the item to a human.

## When the provider cannot be reached

A connection error, timeout, rate limit or server error that survives the client library's own retries is not a bad answer and not a failed attempt. The call returns "unavailable", and the run pauses with its state intact until the provider answers again. A provider that refuses the settings (a bad key, an unknown model) stops the run with a message.

## What the harness logs for every call

The call kind, the step, the model slot used, each raw answer and why it was refused, the checked object, how long each attempt and the whole call took, the action performed and its pixel position, the foreground window's title and process, and the time. The prompt itself is not logged. This log is the audit trail.
