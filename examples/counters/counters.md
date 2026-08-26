---
title: Firmware Review Report
subtitle: Sensor node, release candidate 1.4.2-rc1
author: Firmware Quality Board
date: 2026-03-12
language: english
toc: true
counters:
  fw:
    name: Finding
    format: "FW-{n:02d}"
  req:
    name: Requirement
    format: "REQ-{n:03d}"
    start: 100
---

# Scope

This report reviews release candidate 1.4.2-rc1 of the sensor node firmware.
Two numbered series run through it: findings raised by the review board, and
the requirements they are checked against. Both are declared in the YAML front
matter under `counters:`, so TeXSmith allocates the numbers and both backends —
LaTeX and Typst — print the same ones.

The requirement series starts at `100` because it continues the numbering of
the system specification; the finding series starts at `1`, the default. The
board considers one issue blocking, finding @fw:watchdog, which is described
further down — a reference may point forward as well as backward.

# Requirements under review

The four requirements below were selected for this review. The identifier in
the first column is a definition marker, `#{prefix:key}`: it prints the
formatted number and becomes the anchor every later reference links to.

| Id | Requirement | Verification |
| --- | --- | --- |
| #{req:watchdog-reset} | The watchdog shall reset the node within two seconds of a stalled main loop. | Fault injection |
| #{req:ota-rollback} | An interrupted over-the-air update shall leave the previous image bootable. | Power-cut campaign |
| #{req:key-entropy} | The session key shall be derived from at least 128 bits of hardware entropy. | Code review |
| #{req:log-retention} | The node shall retain the last 64 log records across a reset. | Manual inspection |

Requirement @req:key-entropy was added after last year's security audit and had
never been verified before this review.

# Findings

## Summary

The review raised five findings; the three severe ones are summarised below.
As in the requirement table, the identifiers are defined right in the first
column.

| Id | Severity | Component | Summary |
| --- | --- | --- | --- |
| #{fw:watchdog} | Blocking | `hal/watchdog.c` | The watchdog is fed from the I2C completion handler. |
| #{fw:ota-brick} | Blocking | `ota/apply.c` | A power cut during the swap leaves no bootable image. |
| #{fw:key-entropy} | Major | `crypto/session.c` | The session key is seeded from the boot counter. |

## Watchdog fed from an interrupt handler

Feeding the watchdog from the I2C completion handler means the timer keeps
being serviced while the main loop is stalled on a contended bus. Finding
@fw:watchdog therefore violates @req:watchdog-reset — on a saturated bus the
node stayed unresponsive for more than forty seconds without ever resetting.

## Over-the-air update leaves no bootable image

The updater erases the active slot before validating the incoming image. A
power cut in that window bricks the node, which is exactly what
@[req:ota-rollback] forbids; see @fw:ota-brick.

## Session key seeded from the boot counter

The seed passed to the key derivation function is the 32-bit boot counter, so a
freshly provisioned node produces a predictable session key. Finding
@fw:key-entropy is raised against @req:key-entropy.

## Log buffer wiped on reset {#fw:log-wrap}

The heading above carries a `{#prefix:key}` attribute, a *silent* definition:
the number appears nowhere in the title, yet the finding is allocated one and
can be referenced like any other. The log ring buffer lives in a `.bss`
section that the startup code zeroes, so no record survives a reset and
@req:log-retention is not met. Finding @fw:log-wrap was reported by the field
team before the review started.

## Additional observation

Definition markers are ordinary inline constructs and work in running prose
too. While reproducing the watchdog campaign we also noticed #{fw:rtc-drift},
the real-time clock drifting by roughly four seconds a day at 60 °C. No
requirement covers clock accuracy, so this finding is recorded for information
only.

# Follow-up

Findings @fw:watchdog and @fw:ota-brick block the release and must be fixed in
1.4.2-rc2. Finding @fw:key-entropy is scheduled for 1.5.0 together with the
hardware entropy source. The remaining two, @fw:log-wrap and @fw:rtc-drift, are
deferred to the maintenance backlog.

A reference prints the number and nothing else — `FW-01`, not `Finding FW-01`.
The surrounding noun is written by the author, exactly as for a section
cross-reference; the `name:` field of the counter is only used in TeXSmith's
diagnostics.

# A note on undeclared prefixes

A marker is substituted only when its prefix is declared in the front matter.
The firmware's Ruby log formatter interpolates values into its message
template: spelled out in prose, it uses #{node.id} for the node identifier and
#{sensor:temp} for the reading. Neither `node` nor `sensor` is a declared
counter, so both markers survive into the PDF unchanged — Ruby and CoffeeScript
interpolations are never mangled, and no warning is emitted. Only `fw` and
`req` are declared here, and only those are substituted.
