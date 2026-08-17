# RenderDoc MCP operations

## Connection gate

Before analysis:

1. Open the `.rdc` in qrenderdoc.
2. Confirm the RenderDoc MCP extension is enabled.
3. Call `get_capture_status`.
4. Confirm the returned path/API matches the intended case.

If the capture is still loading, wait. If qrenderdoc reports `Error opening capture` or the log contains `DXGI_ERROR_DEVICE_HUNG`, do not keep polling as if loading were progressing.

## Recommended query order

1. `get_capture_status`
2. `get_frame_summary`
3. `get_draw_calls` with marker filters where possible
4. `get_draw_call_details` for candidates
5. `get_pipeline_state` for relevant events
6. `get_shader_info` for each relevant stage
7. `get_texture_info` before `get_texture_data`
8. `get_buffer_contents` only for bounded ranges until layout is confirmed
9. `find_draws_by_shader`, `find_draws_by_texture`, or `find_draws_by_resource` to trace reuse
10. `get_action_timings` only after narrowing events

## Tool-purpose map

| Tool | Use |
|---|---|
| `get_capture_status` | Identity and loaded-state gate |
| `get_frame_summary` | Pass/action inventory |
| `get_draw_calls` | Hierarchy and marker-local discovery |
| `get_draw_call_details` | Counts, offsets, flags, parents |
| `get_pipeline_state` | Shader/resources/targets/states |
| `get_shader_info` | Full disassembly and reflection |
| `get_texture_info` | Format/dimensions/mips/slices |
| `get_texture_data` | Raw pixel export |
| `get_buffer_contents` | VB/IB/instance/constant data |
| `find_draws_by_shader` | Draw-family grouping |
| `find_draws_by_texture` | Named texture reuse |
| `find_draws_by_resource` | Producer/consumer tracing |
| `get_action_timings` | Measured cost for narrowed events |

## Large-response safeguards

The RenderDoc bridge may use file-based IPC. For large texture/base64 responses:

- wait for the response file size to remain stable across several polls;
- retry JSON parsing while the writer may still be active;
- avoid reading a just-created zero/partial response file;
- export one mip/slice/channel at a time when possible;
- cache successful results locally.

Do not repeatedly request a 4K texture if the first response is merely slow.

## Query discipline

- Filter by marker and candidate event before full-frame resource searches.
- Save returned JSON once; analyze the saved evidence instead of re-querying.
- Inspect resource formats and actual slot indices, not names alone.
- For array/cube/3D textures, record slice/face/depth-slice explicitly.
- Bound buffer reads until stride and range are known.

## Replay-failure diagnosis

Differentiate:

- active loading: CPU/RAM/disk counters change and no fatal log exists;
- UI blocked by modal error: qrenderdoc is responsive but window title/error dialog indicates failure;
- device lost: `DXGI_ERROR_DEVICE_HUNG/REMOVED` in the log;
- likely memory pressure: allocation failure or sustained commit/VRAM exhaustion;
- corrupt/incompatible capture: RDC parsing/version/API errors before replay initialization.

Do not treat a stationary progress bar alone as proof of a hang.
