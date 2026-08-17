---
name: arknights-computer-use
description: Control the Arknights Windows PC client when an operator deployment or other gesture needs one uninterrupted mouse hold across multiple path points. Use for Arknights continuous drags, staged deployment gestures, dwell-at-tile input, or emergency left-button release when the standard computer-use drag cannot preserve the gesture.
---

# Arknights Computer Use

Use the standard computer-use skill for screenshots, window selection, clicks, and all other actions. Use this plugin only for the continuous drag that standard computer-use cannot express.

## Continuous drag

1. Select exactly one returned `Arknights.exe` window titled `明日方舟` with computer-use.
2. Capture a fresh screenshot immediately before the drag. Never reuse coordinates after any state change.
3. Ensure the battle is running. Arknights does not deploy operators while paused.
4. Build `points` in window-relative screenshot coordinates:
   - operator card center;
   - deployment tile center with `dwell_ms` between 100 and 250;
   - facing direction point 60-100 pixels from the tile.
5. Call `arknights_continuous_drag` once. Start with `segment_ms: 180` and `step_ms: 8`.
6. Refresh the screenshot immediately and verify the operator is deployed. Do not retry from stale coordinates.

Example arguments:

```json
{
  "points": [
    { "x": 27, "y": 470, "dwell_ms": 60 },
    { "x": 445, "y": 320, "dwell_ms": 180 },
    { "x": 525, "y": 320, "dwell_ms": 40 }
  ],
  "segment_ms": 180,
  "step_ms": 8
}
```

## Safety

- Operate only the unique visible `Arknights.exe` window titled `明日方舟`; the MCP server enforces this.
- Stop if the user moves the mouse, presses Escape, changes focus, or sends new input.
- Call `arknights_release_mouse` after an interrupted or uncertain drag.
- Test new timings in an in-game practice run before spending sanity.
- Never confirm purchases, recruitment, gacha, premium-currency use, or rare-resource consumption without the user's action-time confirmation.
