"""BlenderAgent gateway: the host-agnostic execution card for Blender.

Mirrors UEAgent's contract (work/UEAgent/skills/ue-mcp-workflows/HOTPATH.md) so
any agent host can drive Blender through Bash: a machine-local route file, a
request built from objects and passed as a file or UTF-8 base64, local waiting,
and a receipt written to an out file. Nothing here depends on an MCP client or
on a particular agent product.

Transport is the addon's own JSON/TCP socket, not the MCP server package. That
is a deliberate trade: telemetry and the safe-mode AST validator both live in
the `blender_mcp` server, so bypassing it removes the telemetry surface
structurally -- and removes the write guard, which this file therefore has to
supply itself (escape-hatch gating, mandatory readback, save gated on a passing
readback, command-id replay).

Request:
  tool            addon command type, e.g. get_scene_info / execute_code,
                  or the job verbs job_status / job_cancel / job_kinds
  arguments       params for that command
  readOnly        true for queries; caller-declared, not a sandbox
  commandId       stable id, required for every mutation and for every job
  readback        {tool, arguments, expect} -- one typed target, required for mutations
  save            {filepath, copy} -- only honoured after a passing readback
  escapeHatch     {reason} -- required to run execute_code, or a job's inline code
  job             submit a background job; implies wait=false semantics
  wait            false without a job is refused: the addon bridge is main-thread
                  blocking, so an async socket call would only hide the freeze

Job object -- exactly one of kind, script or code:
  kind            bounded operation. The gateway owns the Python and declares the
                  postconditions; query `job_kinds` for the catalog and schemas.
                    export   glb/fbx of the scene, the selection, or named objects
                    render   one still frame to PNG. Animation is refused: a frame
                             sequence is not a single verifiable artifact.
                    convert  BVH -> FBX for UE, the proven Kinesis recipe, which
                             skins a dummy cube to the root bone because UE will
                             not build a SkeletalMesh from a geometry-less FBX
  params          the kind's parameters, schema-validated. Unknown names, wrong
                  types, disallowed enum values, wrong file suffixes and missing
                  input files are all refused before any process is started.
  script          path to a .py run by a background Blender
  code            inline string instead of script; needs escapeHatch.reason
  blendFile       optional .blend to open; omit for a deterministic factory startup
  factoryStartup  defaults to true when blendFile is absent, which also keeps the
                  addon out of the job process so it cannot fight the GUI over 9876
  args            extra argv after `--`
  expectArtifacts required for script/code jobs only. A bounded kind declares its
                  own artifacts, so supplying both is refused.
  timeoutSeconds  reported as state "timeout" once exceeded while still running

A job runs in its own `blender --background` process, launched detached so it
outlives this gateway. That separation is what makes cancellation possible at all
-- the addon bridge has no cancel path -- and job scripts never pass through the
`blender_mcp` server, so its safe-mode validator does not apply to them.

Poll states: running, succeeded, failed, crashed (process gone, no status
written), timeout, cancelled. Success is only reported once expectArtifacts
verify, so a job that exits cleanly without producing its output still fails.

expect semantics match UEAgent: object fields match a subset, arrays match
exactly, numbers compare within 1e-6.
"""

import argparse
import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid

NUMBER_TOL = 1e-6
RAW_CODE_TOOLS = {"execute_code", "execute_blender_code"}
LEDGER_NAME = "commands.json"

SAVE_CODE = """
import bpy
bpy.ops.wm.save_as_mainfile(filepath={filepath!r}, copy={copy!r})
print("SAVED_MAINFILE")
"""


class Rejected(Exception):
    """A request that never reached Blender."""


def send_command(route, tool, arguments, timeout):
    """One command per connection; replies are bare JSON with no framing."""
    request = json.dumps({"type": tool, "params": arguments or {}}).encode("utf-8")
    started = time.perf_counter()
    with socket.create_connection((route["host"], route["port"]), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(request)
        buffer = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                raise Rejected("connection closed before a complete reply")
            buffer += chunk
            try:
                reply = json.loads(buffer.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            return (time.perf_counter() - started) * 1000, reply


def canonical(request):
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


MAX_LEDGER_REPLY = 4000


def trim_receipt(receipt):
    """Keep the ledger readable; a screenshot reply is a large base64 blob."""
    trimmed = dict(receipt)
    encoded = json.dumps(trimmed.get("reply"), ensure_ascii=False)
    if len(encoded) > MAX_LEDGER_REPLY:
        trimmed["reply"] = {
            "trimmed": True,
            "chars": len(encoded),
            "status": (receipt.get("reply") or {}).get("status"),
        }
    return trimmed


def load_ledger(route_file):
    path = os.path.join(os.path.dirname(os.path.abspath(route_file)), LEDGER_NAME)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return path, json.load(handle)
        except (json.JSONDecodeError, OSError):
            return path, {}
    return path, {}


def store_ledger(path, ledger):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(ledger, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def compare(actual, expected, trail=""):
    """UEAgent expect semantics: subset for objects, exact for arrays, 1e-6 for numbers."""
    checks = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [{"path": trail or "$", "actual": actual, "expected": expected, "ok": False}]
        for key, want in expected.items():
            checks.extend(compare(actual.get(key), want, f"{trail}.{key}" if trail else key))
        return checks
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return [{"path": trail or "$", "actual": actual, "expected": expected, "ok": False}]
        for index, want in enumerate(expected):
            checks.extend(compare(actual[index], want, f"{trail}[{index}]"))
        return checks
    if isinstance(expected, bool) or isinstance(actual, bool):
        ok = actual is expected or actual == expected
    elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        ok = abs(float(actual) - float(expected)) <= NUMBER_TOL
    else:
        ok = actual == expected
    return [{"path": trail or "$", "actual": actual, "expected": expected, "ok": ok}]


def extract_body(reply):
    """The addon nests payload under result, and execute_code nests stdout again."""
    if reply.get("status") != "success":
        return None
    result = reply.get("result")
    if isinstance(result, dict) and "result" in result and set(result) <= {"executed", "result"}:
        return result["result"]
    return result


JOBS_DIRNAME = "jobs"
WIN_DETACHED_PROCESS = 0x00000008
WIN_CREATE_NEW_PROCESS_GROUP = 0x00000200

RUNNER_TEMPLATE = '''"""Generated by bl_gateway.py. Runs the job target and records its outcome."""
import json
import os
import time
import traceback

import bpy

STATUS_PATH = @@STATUS_PATH@@
TARGET = @@TARGET@@
JOB_ID = @@JOB_ID@@


def write_status(state, error=None):
    record = {
        "jobId": JOB_ID,
        "state": state,
        "error": error,
        "finishedAt": time.time(),
        "blender": bpy.app.version_string,
    }
    tmp = STATUS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, STATUS_PATH)


print("[job " + JOB_ID + "] runner start target=" + TARGET, flush=True)
try:
    with open(TARGET, "r", encoding="utf-8") as handle:
        source = handle.read()
    namespace = {"__name__": "__main__", "__file__": TARGET}
    exec(compile(source, TARGET, "exec"), namespace)
except SystemExit as exc:
    if exc.code in (None, 0):
        write_status("succeeded")
    else:
        write_status("failed", "SystemExit " + str(exc.code))
except BaseException:
    write_status("failed", traceback.format_exc()[-6000:])
else:
    write_status("succeeded")
print("[job " + JOB_ID + "] runner done", flush=True)
'''


EXPORT_TEMPLATE = '''"""Generated by bl_gateway.py for job kind 'export'."""
import os

import bpy

OUT = @@FILEPATH@@
FORMAT = @@FORMAT@@
NAMES = @@OBJECTNAMES@@
SELECTION_ONLY = @@SELECTIONONLY@@
APPLY_MODIFIERS = @@APPLYMODIFIERS@@
ANIMATIONS = @@ANIMATIONS@@

MODULE = "io_scene_fbx" if FORMAT == "fbx" else "io_scene_gltf2"
if MODULE not in bpy.context.preferences.addons:
    bpy.ops.preferences.addon_enable(module=MODULE)

use_selection = SELECTION_ONLY
if NAMES:
    missing = [n for n in NAMES if bpy.data.objects.get(n) is None]
    if missing:
        raise RuntimeError("objects not found in scene: " + ", ".join(missing))
    bpy.ops.object.select_all(action="DESELECT")
    for name in NAMES:
        target = bpy.data.objects[name]
        for item in [target, *target.children_recursive]:
            item.select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[NAMES[0]]
    use_selection = True

os.makedirs(os.path.dirname(OUT), exist_ok=True)
if FORMAT == "glb":
    bpy.ops.export_scene.gltf(
        filepath=OUT,
        export_format="GLB",
        use_selection=use_selection,
        export_apply=APPLY_MODIFIERS,
        export_animations=ANIMATIONS,
    )
else:
    bpy.ops.export_scene.fbx(
        filepath=OUT,
        use_selection=use_selection,
        use_mesh_modifiers=APPLY_MODIFIERS,
        bake_anim=ANIMATIONS,
        apply_scale_options="FBX_SCALE_ALL",
        add_leaf_bones=False,
    )
print("EXPORTED", OUT, os.path.getsize(OUT), "bytes", flush=True)
'''

RENDER_TEMPLATE = '''"""Generated by bl_gateway.py for job kind 'render'."""
import os

import bpy

OUT = @@FILEPATH@@
ENGINE = @@ENGINE@@
WIDTH = @@WIDTH@@
HEIGHT = @@HEIGHT@@
SAMPLES = @@SAMPLES@@
FRAME = @@FRAME@@
CAMERA = @@CAMERA@@

# Enable Cycles before selecting it. The engine enum does not reliably list
# CYCLES even when CYCLES is assignable, and assigning an engine name does not
# raise, so an unregistered engine cannot be detected from the enum and would
# fail silently inside a background job where nobody is watching.
if ENGINE == "CYCLES" and "cycles" not in bpy.context.preferences.addons:
    bpy.ops.preferences.addon_enable(module="cycles")

scene = bpy.context.scene
if CAMERA:
    camera = bpy.data.objects.get(CAMERA)
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("camera object missing or not a CAMERA: " + str(CAMERA))
    scene.camera = camera
if scene.camera is None:
    raise RuntimeError("scene has no camera to render from")
if ENGINE:
    scene.render.engine = ENGINE
if WIDTH:
    scene.render.resolution_x = WIDTH
if HEIGHT:
    scene.render.resolution_y = HEIGHT
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
if SAMPLES and scene.render.engine == "CYCLES":
    scene.cycles.samples = SAMPLES
if FRAME is not None:
    scene.frame_set(FRAME)
scene.render.filepath = OUT
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.render.render(write_still=True)
print("RENDERED", OUT, os.path.getsize(OUT), "bytes", flush=True)
'''

CONVERT_TEMPLATE = '''"""Generated by bl_gateway.py for job kind 'convert' (BVH -> FBX for UE).

Recipe promoted from the proven Kinesis batch converter rather than reinvented:
UE will not build a SkeletalMesh from an FBX carrying no geometry, so a dummy
cube is skinned to the root bone, and the bone axes and nodetype are what the UE
importer was verified against.
"""
import os

import bpy

SRC = @@BVHPATH@@
OUT = @@FILEPATH@@
SCALE_LENGTH = @@SCALELENGTH@@
ROOT_BONE = @@ROOTBONE@@
DUMMY_SIZE = @@DUMMYSIZE@@
DUMMY_HEIGHT = @@DUMMYHEIGHT@@

bpy.ops.wm.read_factory_settings(use_empty=True)
if "io_scene_fbx" not in bpy.context.preferences.addons:
    bpy.ops.preferences.addon_enable(module="io_scene_fbx")

scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = SCALE_LENGTH
bpy.ops.import_anim.bvh(filepath=SRC, update_scene_fps=True, update_scene_duration=True)

armature = next((o for o in scene.objects if o.type == "ARMATURE"), None)
if armature is None:
    raise RuntimeError("no ARMATURE object after BVH import: " + SRC)

bpy.ops.mesh.primitive_cube_add(size=DUMMY_SIZE, location=(0.0, 0.0, DUMMY_HEIGHT))
dummy = bpy.context.active_object
dummy.name = "ConvertDummy"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.select_all(action="DESELECT")
dummy.select_set(True)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.parent_set(type="ARMATURE_NAME")

group = dummy.vertex_groups.get(ROOT_BONE)
if group is None:
    raise RuntimeError("root bone " + repr(ROOT_BONE) + " produced no vertex group on the dummy")
for vertex in dummy.data.vertices:
    group.add([vertex.index], 1.0, "REPLACE")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.fbx(
    filepath=OUT,
    object_types={"ARMATURE", "MESH"},
    add_leaf_bones=False,
    bake_anim=True,
    bake_anim_simplify_factor=0.0,
    primary_bone_axis="Y",
    secondary_bone_axis="X",
    armature_nodetype="NULL",
    apply_scale_options="FBX_SCALE_ALL",
)
print("CONVERTED", OUT, os.path.getsize(OUT), "bytes", flush=True)
'''


def normalize_export(resolved):
    path = resolved["filepath"]
    fmt = resolved.get("format")
    if fmt is None:
        lowered = path.lower()
        fmt = "fbx" if lowered.endswith(".fbx") else "glb" if lowered.endswith(".glb") else None
        if fmt is None:
            raise Rejected(
                "job kind export: filepath must end with .glb or .fbx, or set params.format")
    if not path.lower().endswith("." + fmt):
        raise Rejected(
            f"job kind export: filepath {path!r} does not match format {fmt!r}; "
            "the expected artifact has to be exact")
    resolved["format"] = fmt
    return resolved


JOB_KINDS = {
    "export": {
        "summary": "glb or fbx export of the whole scene, the selection, or named objects",
        "params": {
            "filepath": {"type": str, "required": True, "path": True},
            "format": {"type": str, "default": None, "allowed": ("glb", "fbx")},
            "objectNames": {"type": list, "item_type": str, "default": None},
            "selectionOnly": {"type": bool, "default": False},
            "applyModifiers": {"type": bool, "default": True},
            "animations": {"type": bool, "default": True},
        },
        "template": EXPORT_TEMPLATE,
        "normalize": normalize_export,
        "artifacts": lambda resolved: [resolved["filepath"]],
    },
    "render": {
        "summary": "one still frame to PNG; animation is refused because a frame "
                   "sequence is not a single verifiable artifact",
        "params": {
            "filepath": {"type": str, "required": True, "path": True, "suffix": ".png"},
            "engine": {"type": str, "default": None,
                       "allowed": ("CYCLES", "BLENDER_EEVEE_NEXT")},
            "width": {"type": int, "default": None},
            "height": {"type": int, "default": None},
            "samples": {"type": int, "default": None},
            "frame": {"type": int, "default": None},
            "camera": {"type": str, "default": None},
        },
        "template": RENDER_TEMPLATE,
        "artifacts": lambda resolved: [resolved["filepath"]],
    },
    "convert": {
        "summary": "BVH to FBX for UE import, using the proven Kinesis recipe",
        "params": {
            "bvhPath": {"type": str, "required": True, "path": True, "input": True},
            "filepath": {"type": str, "required": True, "path": True, "suffix": ".fbx"},
            "scaleLength": {"type": float, "default": 0.01},
            "rootBone": {"type": str, "default": "Hips"},
            "dummySize": {"type": float, "default": 1.0},
            "dummyHeight": {"type": float, "default": 100.0},
        },
        "template": CONVERT_TEMPLATE,
        "artifacts": lambda resolved: [resolved["filepath"]],
    },
}


def describe_kinds():
    """Render the manifest as a catalog, so the bounded surface is discoverable on demand."""
    kinds = {}
    for name, spec in JOB_KINDS.items():
        params = {}
        for param_name, rule in spec["params"].items():
            described = {
                "type": rule["type"].__name__,
                "required": bool(rule.get("required")),
                "default": rule.get("default"),
            }
            if rule.get("allowed"):
                described["allowed"] = list(rule["allowed"])
            if rule.get("suffix"):
                described["suffix"] = rule["suffix"]
            if rule.get("input"):
                described["mustExist"] = True
            params[param_name] = described
        kinds[name] = {"summary": spec["summary"], "params": params}
    return {"outcome": "succeeded", "tool": "job_kinds", "readOnly": True, "kinds": kinds,
            "reply": None, "readback": None, "save": None, "error": None}


def check_type(kind, name, value, rule):
    want = rule["type"]
    if want is bool:
        if not isinstance(value, bool):
            raise Rejected(f"job kind {kind}: '{name}' must be a boolean, got {value!r}")
    elif want is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise Rejected(f"job kind {kind}: '{name}' must be an integer, got {value!r}")
    elif want is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise Rejected(f"job kind {kind}: '{name}' must be a number, got {value!r}")
    elif want is str:
        if not isinstance(value, str):
            raise Rejected(f"job kind {kind}: '{name}' must be a string, got {value!r}")
    elif want is list:
        if not isinstance(value, list):
            raise Rejected(f"job kind {kind}: '{name}' must be a list, got {value!r}")
        item_type = rule.get("item_type")
        if item_type and any(not isinstance(item, item_type) for item in value):
            raise Rejected(
                f"job kind {kind}: '{name}' must contain only {item_type.__name__} items")


def validate_params(kind, params):
    spec = JOB_KINDS[kind]["params"]
    given = dict(params or {})
    unknown = sorted(set(given) - set(spec))
    if unknown:
        raise Rejected(
            f"job kind {kind}: unknown params {unknown}; allowed are {sorted(spec)}")
    resolved = {}
    for name, rule in spec.items():
        value = given.get(name)
        if value is None:
            if rule.get("required"):
                raise Rejected(f"job kind {kind}: missing required param '{name}'")
            value = rule.get("default")
        else:
            check_type(kind, name, value, rule)
        allowed = rule.get("allowed")
        if allowed and value is not None and value not in allowed:
            raise Rejected(
                f"job kind {kind}: '{name}' must be one of {list(allowed)}, got {value!r}")
        if rule.get("path") and value:
            value = os.path.abspath(value)
            if rule.get("input") and not os.path.exists(value):
                raise Rejected(f"job kind {kind}: '{name}' does not exist: {value}")
        suffix = rule.get("suffix")
        if suffix and value and not str(value).lower().endswith(suffix):
            raise Rejected(
                f"job kind {kind}: '{name}' must end with {suffix} so the expected artifact "
                f"is exact, got {value!r}")
        resolved[name] = value
    return resolved


def prepare_kind_job(kind, params, directory, job_id):
    """Validate, normalize and materialize a bounded job; return (script, artifacts, params)."""
    spec = JOB_KINDS[kind]
    resolved = validate_params(kind, params)
    normalize = spec.get("normalize")
    if normalize:
        resolved = normalize(resolved)
    source = spec["template"]
    for name, value in resolved.items():
        source = source.replace("@@" + name.upper() + "@@", repr(value))
    if "@@" in source:
        leftover = sorted({token for token in source.split("@@")[1::2]})
        raise Rejected(f"job kind {kind}: template placeholders left unfilled: {leftover}")
    target = os.path.join(directory, f"{job_id}-{kind}.py")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(source)
    artifacts = [os.path.abspath(p) for p in spec["artifacts"](resolved)]
    return target, artifacts, resolved


def jobs_dir(route_file):
    return os.path.join(os.path.dirname(os.path.abspath(route_file)), JOBS_DIRNAME)


def process_alive(pid):
    """Liveness without side effects.

    os.kill(pid, 0) is not a probe on Windows: CPython routes any signal other
    than CTRL_C_EVENT/CTRL_BREAK_EVENT to TerminateProcess, which would kill the
    very job being checked.
    """
    if not pid:
        return False
    if sys.platform == "win32":
        probe = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        return str(int(pid)) in (probe.stdout or "")
    return os.path.exists(f"/proc/{int(pid)}")


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def verify_artifacts(paths, since):
    """Existence is not enough: the artifact must be non-empty and newer than the job."""
    verified = []
    for path in paths:
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        fresh = bool(exists and os.stat(path).st_mtime >= since - 1)
        verified.append({"path": path, "exists": exists, "bytes": size,
                         "fresh": fresh, "ok": bool(exists and size > 0 and fresh)})
    return verified


def tail(path, limit=2000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()[-limit:]
    except OSError:
        return None


def job_record_path(route_file, job_id):
    return os.path.join(jobs_dir(route_file), f"{job_id}.json")


def submit_job(route, request, route_file):
    job = request["job"]
    command_id = request.get("commandId")
    if not command_id:
        raise Rejected("a job requires a stable commandId, so a retry cannot launch a second process")

    ledger_path, ledger = load_ledger(route_file)
    digest = canonical(request)
    known = ledger.get(command_id)
    if known:
        if known.get("hash") != digest:
            raise Rejected(f"commandId {command_id} was already used by a different request")
        if known.get("terminal"):
            return dict(known["receipt"], outcome="replayed")

    kind = job.get("kind")
    script, code = job.get("script"), job.get("code")
    supplied = [name for name, value in (("kind", kind), ("script", script), ("code", code))
                if value]
    if len(supplied) != 1:
        raise Rejected(f"job needs exactly one of kind, script or code; got {supplied or 'none'}")
    if code and not (request.get("escapeHatch") or {}).get("reason"):
        raise Rejected(
            "job.code is arbitrary bpy and needs escapeHatch.reason; prefer a bounded job.kind")
    if kind and kind not in JOB_KINDS:
        raise Rejected(f"unknown job kind {kind!r}; known kinds are {sorted(JOB_KINDS)}")
    if kind and job.get("expectArtifacts"):
        raise Rejected(f"job kind {kind} declares its own postconditions; drop expectArtifacts")

    blender = route.get("blenderPath") or os.environ.get("BLENDER_PATH")
    if not blender or not os.path.exists(blender):
        raise Rejected(f"no usable Blender executable: {blender!r}")

    directory = jobs_dir(route_file)
    os.makedirs(directory, exist_ok=True)
    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    status_path = os.path.join(directory, f"{job_id}.status.json")
    log_path = os.path.join(directory, f"{job_id}.log")
    record_path = job_record_path(route_file, job_id)

    resolved_params = None
    if kind:
        target, expected, resolved_params = prepare_kind_job(
            kind, job.get("params"), directory, job_id)
    else:
        expected = job.get("expectArtifacts") or []
        if not expected:
            raise Rejected(
                "job.expectArtifacts is required for a script/code job; a bounded job.kind "
                "declares its own postconditions, so prefer it")
        if script:
            target = os.path.abspath(script)
            if not os.path.exists(target):
                raise Rejected(f"job.script does not exist: {target}")
        else:
            target = os.path.join(directory, f"{job_id}.py")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(code)

    runner_path = os.path.join(directory, f"{job_id}-runner.py")
    runner = (RUNNER_TEMPLATE
              .replace("@@STATUS_PATH@@", json.dumps(status_path))
              .replace("@@TARGET@@", json.dumps(target))
              .replace("@@JOB_ID@@", json.dumps(job_id)))
    with open(runner_path, "w", encoding="utf-8") as handle:
        handle.write(runner)

    blend_file = job.get("blendFile")
    if blend_file:
        blend_file = os.path.abspath(blend_file)
        if not os.path.exists(blend_file):
            raise Rejected(f"job.blendFile does not exist: {blend_file}")
    # Without a blend file, factory startup keeps the run deterministic and also
    # keeps the addon out of the process, so it cannot fight the GUI over port 9876.
    factory = job.get("factoryStartup", blend_file is None)
    argv = [blender, "--background"]
    if blend_file:
        argv.append(blend_file)
    elif factory:
        argv.append("--factory-startup")
    argv += ["--python", runner_path]
    extra = job.get("args") or []
    if extra:
        argv += ["--"] + [str(item) for item in extra]

    started = time.time()
    log_handle = open(log_path, "wb")
    try:
        if sys.platform == "win32":
            # Detached so the job outlives this gateway process, which exits per call.
            process = subprocess.Popen(
                argv, stdout=log_handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                cwd=directory, close_fds=True,
                creationflags=WIN_DETACHED_PROCESS | WIN_CREATE_NEW_PROCESS_GROUP)
        else:
            process = subprocess.Popen(
                argv, stdout=log_handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                cwd=directory, close_fds=True, start_new_session=True)
    finally:
        log_handle.close()

    record = {
        "jobId": job_id, "commandId": command_id, "pid": process.pid, "startedAt": started,
        "argv": argv, "target": target, "blendFile": blend_file,
        "kind": kind, "params": resolved_params,
        "expectArtifacts": [os.path.abspath(p) for p in expected],
        "timeoutSeconds": job.get("timeoutSeconds"),
        "statusPath": status_path, "logPath": log_path, "recordPath": record_path,
        "escapeHatch": request.get("escapeHatch"),
    }
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)

    receipt = {
        "outcome": "submitted", "commandId": command_id, "jobId": job_id, "pid": process.pid,
        "tool": "job", "readOnly": False, "elapsedMs": round((time.time() - started) * 1000, 1),
        "state": "running", "kind": kind, "params": resolved_params,
        "argv": argv, "logPath": log_path, "recordPath": record_path,
        "expectArtifacts": record["expectArtifacts"], "reply": None, "readback": None,
        "save": None, "error": None,
        "route": {k: route.get(k) for k in
                  ("host", "port", "protocolVersion", "addonVersion", "blenderVersion")},
    }
    ledger[command_id] = {"hash": digest, "terminal": True, "receipt": trim_receipt(receipt)}
    store_ledger(ledger_path, ledger)
    return receipt


def resolve_state(record):
    """Status file wins; then liveness; a vanished process with no status crashed."""
    if record.get("cancelledAt"):
        return "cancelled"
    status = read_json(record["statusPath"])
    if status and status.get("state"):
        return status["state"]
    if process_alive(record.get("pid")):
        timeout = record.get("timeoutSeconds")
        if timeout and (time.time() - record["startedAt"]) > float(timeout):
            return "timeout"
        return "running"
    return "crashed"


def poll_job(request, route_file):
    arguments = request.get("arguments") or {}
    job_id = arguments.get("jobId") or request.get("jobId")
    if not job_id:
        raise Rejected("job_status requires arguments.jobId")
    record = read_json(job_record_path(route_file, job_id))
    if not record:
        raise Rejected(f"unknown jobId {job_id}")

    state = resolve_state(record)
    status = read_json(record["statusPath"]) or {}
    elapsed = (status.get("finishedAt") or time.time()) - record["startedAt"]
    artifacts = verify_artifacts(record["expectArtifacts"], record["startedAt"])
    artifacts_ok = all(item["ok"] for item in artifacts)

    if state == "succeeded" and not artifacts_ok:
        state = "failed"
        error = "job reported success but its expected artifacts did not verify"
    else:
        error = status.get("error")

    if state == "succeeded":
        outcome = "succeeded"
    elif state in ("running", "timeout"):
        outcome = "running"
    elif state == "cancelled":
        # Distinct from failed: the caller stopped it, it did not break.
        outcome = "cancelled"
    else:
        outcome = "failed"

    return {
        "outcome": outcome, "commandId": record.get("commandId"), "jobId": job_id,
        "tool": "job_status", "readOnly": True, "state": state,
        "kind": record.get("kind"), "params": record.get("params"),
        "elapsedSeconds": round(elapsed, 2), "pid": record.get("pid"),
        "alive": process_alive(record.get("pid")),
        "blender": status.get("blender"), "artifacts": artifacts,
        "logTail": tail(record["logPath"]), "logPath": record["logPath"],
        "reply": status or None, "readback": None, "save": None, "error": error,
    }


def cancel_job(request, route_file):
    arguments = request.get("arguments") or {}
    job_id = arguments.get("jobId") or request.get("jobId")
    if not job_id:
        raise Rejected("job_cancel requires arguments.jobId")
    record_path = job_record_path(route_file, job_id)
    record = read_json(record_path)
    if not record:
        raise Rejected(f"unknown jobId {job_id}")
    if record.get("cancelledAt"):
        return {"outcome": "replayed", "jobId": job_id, "tool": "job_cancel",
                "state": "cancelled", "error": None,
                "detail": f"already cancelled at {record['cancelledAt']}"}

    pid = record.get("pid")
    alive = process_alive(pid)
    killed = None
    if alive:
        if sys.platform == "win32":
            proc = subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            killed = proc.returncode == 0
        else:
            try:
                os.killpg(os.getpgid(int(pid)), 15)
                killed = True
            except OSError as exc:
                killed = False
                record["cancelError"] = f"{type(exc).__name__}: {exc}"
    record["cancelledAt"] = time.time()
    record["wasAlive"] = alive
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
    return {
        "outcome": "succeeded" if (killed or not alive) else "failed",
        "commandId": request.get("commandId"), "jobId": job_id, "tool": "job_cancel",
        "readOnly": False, "state": "cancelled", "wasAlive": alive, "killed": killed,
        "reply": None, "readback": None, "save": None,
        "error": None if (killed or not alive) else "process survived the kill request",
    }


def init_route(route_file, timeout):
    """Resolve BLENDER_PATH, probe the addon, and write the machine-local route."""
    blender_path = os.environ.get("BLENDER_PATH", "")
    if not blender_path or not os.path.exists(blender_path):
        raise Rejected(f"BLENDER_PATH is unset or missing: {blender_path!r}")
    probe = {"host": "127.0.0.1", "port": 9876}
    _, ping = send_command(probe, "ping", {}, timeout)
    if ping.get("status") != "success":
        raise Rejected(f"addon did not answer ping: {ping}")
    _, info = send_command(probe, "get_addon_info", {}, timeout)
    payload = extract_body(info) or {}
    route = {
        "host": probe["host"],
        "port": probe["port"],
        "blenderPath": blender_path,
        "protocolVersion": payload.get("protocol_version"),
        "addonVersion": payload.get("addon_version"),
        "blenderVersion": payload.get("blender_version"),
        "capabilities": payload.get("capabilities"),
        "generatedAt": time.time(),
    }
    os.makedirs(os.path.dirname(os.path.abspath(route_file)), exist_ok=True)
    with open(route_file, "w", encoding="utf-8") as handle:
        json.dump(route, handle, ensure_ascii=False, indent=2)
    return route


def execute(route, request, route_file, timeout):
    tool = request.get("tool")
    arguments = request.get("arguments") or {}
    read_only = bool(request.get("readOnly"))
    command_id = request.get("commandId")
    readback = request.get("readback")
    save = request.get("save")
    receipt = {
        "outcome": "failed",
        "commandId": command_id,
        "tool": tool,
        "readOnly": read_only,
        "elapsedMs": None,
        "reply": None,
        "readback": None,
        "save": None,
        "error": None,
        "route": {k: route.get(k) for k in
                  ("host", "port", "protocolVersion", "addonVersion", "blenderVersion")},
    }

    if request.get("job"):
        return submit_job(route, request, route_file)
    if tool == "job_status":
        return poll_job(request, route_file)
    if tool == "job_cancel":
        return cancel_job(request, route_file)
    if tool == "job_kinds":
        return describe_kinds()

    if not tool:
        raise Rejected("request.tool is required")
    if request.get("wait") is False:
        raise Rejected(
            "wait=false needs a job request; the addon bridge is main-thread blocking, so an "
            "asynchronous socket call would only hide the freeze. Submit a job instead.")

    # Command-id replay: identical canonical request returns the recorded terminal
    # result without touching Blender; a different request under a used id is refused.
    ledger_path, ledger = load_ledger(route_file)
    digest = canonical(request)
    if not read_only:
        if not command_id:
            raise Rejected("mutations require a stable commandId")
        if not readback:
            raise Rejected("mutations require a readback target; a write without verification is refused")
        known = ledger.get(command_id)
        if known:
            if known.get("hash") != digest:
                raise Rejected(f"commandId {command_id} was already used by a different request")
            if known.get("terminal"):
                return dict(known["receipt"], outcome="replayed")
        ledger[command_id] = {"hash": digest, "terminal": False}
        store_ledger(ledger_path, ledger)

    if tool in RAW_CODE_TOOLS:
        reason = (request.get("escapeHatch") or {}).get("reason")
        if not reason:
            raise Rejected(
                f"{tool} is arbitrary bpy and needs escapeHatch.reason; "
                "prefer a bounded tool, and keep blocking work on the CLI route")

    elapsed, reply = send_command(route, tool, arguments, timeout)
    receipt["elapsedMs"] = round(elapsed, 1)
    receipt["reply"] = reply
    if reply.get("status") != "success":
        receipt["error"] = reply.get("message")
        return receipt

    # The addon can report success at the transport level and still carry a
    # command error in the body, e.g. get_viewport_screenshot without a filepath
    # answers {"status":"success","result":{"error":"No filepath provided"}}.
    body = extract_body(reply)
    if isinstance(body, dict) and body.get("error"):
        receipt["error"] = body["error"]
        return receipt

    if readback:
        rb_elapsed, rb_reply = send_command(
            route, readback["tool"], readback.get("arguments") or {}, timeout)
        body = extract_body(rb_reply)
        checks = compare(body, readback.get("expect") or {})
        passed = rb_reply.get("status") == "success" and all(c["ok"] for c in checks)
        receipt["readback"] = {
            "tool": readback["tool"], "passed": passed, "elapsedMs": round(rb_elapsed, 1),
            "checks": checks, "body": body,
        }
        if not passed:
            receipt["error"] = "readback failed"
            return receipt

    if save:
        # A failed verification cannot save, and the save code is gateway-owned so
        # the caller cannot smuggle path work past the escape-hatch gate.
        filepath = save.get("filepath")
        if not filepath:
            raise Rejected("save.filepath is required")
        run_started = time.time()
        save_elapsed, save_reply = send_command(
            route, "execute_code",
            {"code": SAVE_CODE.format(filepath=filepath.replace("\\", "/"),
                                       copy=bool(save.get("copy", True)))},
            timeout)
        exists = os.path.exists(filepath)
        size = os.path.getsize(filepath) if exists else 0
        # Freshness matters: a stale artifact from an earlier run is not this save.
        is_fresh = exists and os.stat(filepath).st_mtime >= run_started - 1
        receipt["save"] = {
            "passed": save_reply.get("status") == "success" and exists and size > 0 and is_fresh,
            "filepath": filepath, "bytes": size, "fresh": is_fresh,
            "elapsedMs": round(save_elapsed, 1), "reply": extract_body(save_reply),
        }
        if not receipt["save"]["passed"]:
            receipt["error"] = "save did not produce a fresh artifact"
            return receipt

    receipt["outcome"] = "succeeded"
    receipt["error"] = None
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description="BlenderAgent gateway")
    parser.add_argument("--route-file", required=True)
    parser.add_argument("--request-file")
    parser.add_argument("--request-base64")
    parser.add_argument("--out-file")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--init-route", action="store_true",
                        help="resolve BLENDER_PATH, probe the addon, write the route file")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.init_route:
            route = init_route(args.route_file, args.timeout)
            receipt = {"outcome": "route_ready", "route": route}
        else:
            if args.request_base64:
                raw = base64.b64decode(args.request_base64).decode("utf-8")
            elif args.request_file:
                with open(args.request_file, "r", encoding="utf-8") as handle:
                    raw = handle.read()
            else:
                raise Rejected("pass --request-file or --request-base64")
            request = json.loads(raw)
            with open(args.route_file, "r", encoding="utf-8") as handle:
                route = json.load(handle)
            receipt = execute(route, request, args.route_file, args.timeout)
            if request.get("commandId") and not request.get("readOnly"):
                ledger_path, ledger = load_ledger(args.route_file)
                entry = ledger.get(request["commandId"])
                if entry is not None:
                    entry["terminal"] = True
                    entry["receipt"] = trim_receipt(receipt)
                    store_ledger(ledger_path, ledger)
    except Rejected as exc:
        receipt = {"outcome": "rejected", "error": str(exc)}
    except (OSError, socket.timeout, json.JSONDecodeError) as exc:
        receipt = {"outcome": "failed", "error": f"{type(exc).__name__}: {exc}"}

    text = json.dumps(receipt, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.out_file:
        os.makedirs(os.path.dirname(os.path.abspath(args.out_file)), exist_ok=True)
        with open(args.out_file, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0 if receipt.get("outcome") in (
        "succeeded", "route_ready", "replayed", "submitted", "running") else 1


if __name__ == "__main__":
    sys.exit(main())
