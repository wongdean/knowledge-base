---
name: "context-hygiene"
description: "Suggest whether to use `/compact` when a conversation appears to switch to a new, unrelated task. Use for long-running assistant sessions with mixed topics, especially when the user moves between different machines, projects, incidents, or objectives. Prefer high precision: trigger only on clear task boundaries, and avoid triggering when the next request still depends on prior state, edits, logs, or conclusions."
---

# Context Hygiene

## Overview

Detect clear topic switches and decide whether to suggest `/compact`.
Optimize for low token usage and low false positives.

## Decision Rule

Default to silence.
Suggest `/compact` only when the task switch is obvious and the next step does not rely on current context.

Treat uncertainty as "do not suggest `/compact`".

## Suggest `/compact`

Suggest `/compact` only if all of the following are true:

- The user has clearly switched to a different goal.
- The new goal is unrelated to the current machine, project, incident, or code path.
- The previous task is already complete or parked.
- The next task does not need prior logs, process state, file diffs, server findings, or recent conclusions.

High-confidence examples:

- The user says the new request is unrelated.
- The conversation moves from one project or server to another unrelated one.
- A long debugging thread is finished and the user starts a separate planning or writing task.

## Do Not Suggest `/compact`

Do not suggest `/compact` in these cases:

- The user is continuing the same objective, even if they changed sub-steps.
- The next request asks for explanation, verification, cleanup, or follow-up on the same work.
- The conversation still depends on remote state, runtime state, logs, edits, or recent decisions.
- You are not confident the tasks are independent.
- Suggesting `/compact` would add more friction than value.

## Output Style

Keep the output short.
Use one sentence by default.

Default suggestion:
`This looks unrelated to the current thread; suggest /compact first.`

If a tiny handoff summary is required before suggesting `/compact`, keep it to at most three short lines.
Do not generate a long recap.
Do not explain the full policy unless the user asks.

## Handoff Summary Rule

Before suggesting `/compact`, add a summary only if the next step might lose one or two critical facts.

When you add a summary:

- Keep it under three lines.
- Preserve only the facts needed to resume safely.
- Omit details that can be rediscovered cheaply.

## Anti-Patterns

Avoid these mistakes:

- Suggest `/compact` because the conversation is merely long.
- Suggest `/compact` during active debugging or deployment.
- Produce a recap longer than the saved context is worth.
- Interrupt a clearly connected follow-up request.
