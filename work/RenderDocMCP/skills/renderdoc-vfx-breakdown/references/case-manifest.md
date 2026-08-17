# Case manifest

Create `case.json` in the analysis workspace. Keep paths external to the skill.

## Minimal schema

```json
{
  "case_id": "game-effect-date",
  "scope": {
    "effect": "waterfall",
    "audience": ["vfx", "ta"],
    "requested_deliverables": ["md", "pdf", "pptx", "hlsl", "fbx"]
  },
  "capture": {
    "path": "D:/captures/frame.rdc",
    "executable": "D:/game/game.exe",
    "api": "D3D12",
    "resolution": [3840, 2160],
    "identity_status": "confirmed"
  },
  "authoritative_inputs": {
    "edited_pptx": null,
    "edited_markdown": null,
    "may_overwrite": false
  },
  "subsystems": [
    {
      "name": "principal-mesh",
      "events": [1234],
      "status": "confirmed",
      "evidence": []
    }
  ],
  "claims": [
    {
      "id": "claim-001",
      "text": "The material writes GBuffer properties.",
      "level": "confirmed",
      "events": [1234],
      "resources": ["ResourceId::1"],
      "limits": "Final lighting is evaluated later."
    }
  ],
  "deliverables": {},
  "qa": {
    "status": "pending",
    "checks": []
  }
}
```

## Rules

- Use forward-slash paths in JSON for portability.
- Preserve captured numeric identifiers exactly.
- Do not store large binary/base64 payloads in `case.json`; store file paths and hashes.
- Update claim levels when new evidence changes confidence.
- Record the authoritative edited PPT/MD before modifying anything.
- Record every delivered file with size and SHA-256 during packaging.
