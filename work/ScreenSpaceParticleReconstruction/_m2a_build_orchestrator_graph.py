import json
import unreal

BP = "/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator"
GRAPH = "EventGraph"
service = unreal.BlueprintService


def node(ref, node_type, **params):
    return {"ref": ref, "type": node_type, "params": params}


def connection(source, target):
    return {"from_": source, "to": target}


def default(ref, pin, value):
    return {"node_ref": ref, "pin_name": pin, "value": value}


# This Blueprint was created exclusively for the SSPR M2 pipeline. Rebuilding
# its EventGraph is safe and keeps reruns deterministic.
removed = []
for existing in service.get_nodes_in_graph(BP, GRAPH, 0, "", False):
    node_id = str(existing.node_id)
    if service.delete_node(BP, GRAPH, node_id):
        removed.append(node_id)

nodes = [
    # Initialization
    node("BeginPlay", "event", event="ReceiveBeginPlay", group="Initialize"),
    node("GetNiagaraInit", "variable_get", variable="SSPRNiagara", group="Initialize"),
    node("GetCurrentInit", "variable_get", variable="CurrentRT", group="Initialize"),
    node("GetHistoryAInit", "variable_get", variable="HistoryA", group="Initialize"),
    node("GetHistoryBInit", "variable_get", variable="HistoryB", group="Initialize"),
    node("GetCoreRTInit", "variable_get", variable="CoreRT", group="Initialize"),
    node(
        "GetBlurSmallRTInit",
        "variable_get",
        variable="BlurSmallRT",
        group="Initialize",
    ),
    node(
        "GetBlurLargeRTInit",
        "variable_get",
        variable="BlurLargeRT",
        group="Initialize",
    ),
    node(
        "GetDensityRTInit",
        "variable_get",
        variable="DensityRT",
        group="Initialize",
    ),
    node(
        "GetSmokeRTInit",
        "variable_get",
        variable="SmokeRT",
        group="Initialize",
    ),
    node(
        "GetTemporalMaterial",
        "variable_get",
        variable="TemporalMaterial",
        group="Initialize",
    ),
    node(
        "GetCoreMaterial",
        "variable_get",
        variable="CoreMaterial",
        group="Initialize",
    ),
    node(
        "GetSmallBlurMaterial",
        "variable_get",
        variable="SmallBlurMaterial",
        group="Initialize",
    ),
    node(
        "GetLargeBlurMaterial",
        "variable_get",
        variable="LargeBlurMaterial",
        group="Initialize",
    ),
    node(
        "GetDensityMaterial",
        "variable_get",
        variable="DensityMaterial",
        group="Initialize",
    ),
    node(
        "GetSmokeMaterial",
        "variable_get",
        variable="SmokeMaterial",
        group="Initialize",
    ),
    node(
        "GetSmokeCardInit",
        "variable_get",
        variable="SmokeCard",
        group="Smoke Card",
    ),
    node(
        "GetSmokeCardMaterialInit",
        "variable_get",
        variable="SmokeCardMaterial",
        group="Smoke Card",
    ),
    node(
        "SetNiagaraRT",
        "function_call",
        **{
            "class": "NiagaraComponent",
            "function": "SetVariableTextureRenderTarget",
            "group": "Initialize",
        },
    ),
    node(
        "AddTickPrerequisite",
        "function_call",
        **{
            "class": "Actor",
            "function": "AddTickPrerequisiteComponent",
            "group": "Initialize",
        },
    ),
    node(
        "CreateMID",
        "function_call",
        **{
            "class": "KismetMaterialLibrary",
            "function": "CreateDynamicMaterialInstance",
            "group": "Initialize",
        },
    ),
    node("SetMID", "variable_set", variable="TemporalMID", group="Initialize"),
    node(
        "CreateCoreMID",
        "function_call",
        **{
            "class": "KismetMaterialLibrary",
            "function": "CreateDynamicMaterialInstance",
            "group": "Initialize",
        },
    ),
    node("SetCoreMID", "variable_set", variable="CoreMID", group="Initialize"),
    node(
        "CreateSmallBlurMID",
        "function_call",
        **{
            "class": "KismetMaterialLibrary",
            "function": "CreateDynamicMaterialInstance",
            "group": "Initialize",
        },
    ),
    node(
        "SetSmallBlurMID",
        "variable_set",
        variable="SmallBlurMID",
        group="Initialize",
    ),
    node(
        "CreateLargeBlurMID",
        "function_call",
        **{
            "class": "KismetMaterialLibrary",
            "function": "CreateDynamicMaterialInstance",
            "group": "Initialize",
        },
    ),
    node(
        "SetLargeBlurMID",
        "variable_set",
        variable="LargeBlurMID",
        group="Initialize",
    ),
    node(
        "CreateDensityMID",
        "function_call",
        **{
            "class": "KismetMaterialLibrary",
            "function": "CreateDynamicMaterialInstance",
            "group": "Initialize",
        },
    ),
    node(
        "SetDensityMID",
        "variable_set",
        variable="DensityMID",
        group="Initialize",
    ),
    node(
        "CreateSmokeMID",
        "function_call",
        **{
            "class": "KismetMaterialLibrary",
            "function": "CreateDynamicMaterialInstance",
            "group": "Initialize",
        },
    ),
    node(
        "SetSmokeMID",
        "variable_set",
        variable="SmokeMID",
        group="Initialize",
    ),
    node(
        "SetSmokeCardMaterial",
        "function_call",
        **{
            "class": "PrimitiveComponent",
            "function": "SetMaterial",
            "group": "Smoke Card",
        },
    ),
    node(
        "ClearCurrentInit",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Initialize",
        },
    ),
    node(
        "ClearHistoryAInit",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Initialize",
        },
    ),
    node(
        "ClearHistoryBInit",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Initialize",
        },
    ),
    node(
        "ClearCoreInit",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Initialize",
        },
    ),
    node(
        "ClearBlurSmallInit",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Initialize",
        },
    ),
    node(
        "ClearBlurLargeInit",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Initialize",
        },
    ),
    node(
        "ClearDensityInit",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Initialize",
        },
    ),
    node(
        "ClearSmokeInit",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Initialize",
        },
    ),
    node("SetWriteAInit", "variable_set", variable="bWriteHistoryA", group="Initialize"),
    node(
        "SetValidInit",
        "variable_set",
        variable="HistoryValidValue",
        group="Initialize",
    ),
    node(
        "SetLatestInit",
        "variable_set",
        variable="LatestHistory",
        group="Initialize",
    ),
    node(
        "ActivateNiagara",
        "function_call",
        **{
            "class": "ActorComponent",
            "function": "Activate",
            "group": "Initialize",
        },
    ),
    # Callable reset path
    node(
        "ResetTemporalHistory",
        "custom_event",
        name="ResetTemporalHistory",
        group="Reset",
    ),
    node(
        "ResetClearCurrent",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Reset",
        },
    ),
    node(
        "ResetClearHistoryA",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Reset",
        },
    ),
    node(
        "ResetClearHistoryB",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Reset",
        },
    ),
    node(
        "ResetClearCore",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Reset",
        },
    ),
    node(
        "ResetClearBlurSmall",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Reset",
        },
    ),
    node(
        "ResetClearBlurLarge",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Reset",
        },
    ),
    node(
        "ResetClearDensity",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Reset",
        },
    ),
    node(
        "ResetClearSmoke",
        "function_call",
        **{
            "class": "KismetRenderingLibrary",
            "function": "ClearRenderTarget2D",
            "group": "Reset",
        },
    ),
    node(
        "ResetWriteA",
        "variable_set",
        variable="bWriteHistoryA",
        group="Reset",
    ),
    node(
        "ResetHistoryValid",
        "variable_set",
        variable="HistoryValidValue",
        group="Reset",
    ),
    node(
        "ResetCameraValid",
        "variable_set",
        variable="CameraDataValid",
        group="Reset",
    ),
    node(
        "ResetLatestHistory",
        "variable_set",
        variable="LatestHistory",
        group="Reset",
    ),
    node(
        "ResetNiagara",
        "function_call",
        **{
            "class": "NiagaraComponent",
            "function": "ReinitializeSystem",
            "group": "Reset",
        },
    ),
    # Tick and shared values
    node("Tick", "event", event="ReceiveTick", group="Temporal Tick"),
    node("GetWriteA", "variable_get", variable="bWriteHistoryA", group="Temporal Tick"),
    node("BranchHistory", "branch", group="Temporal Tick"),
    node("GetMIDTick", "variable_get", variable="TemporalMID", group="Temporal Tick"),
    node("GetCurrentTick", "variable_get", variable="CurrentRT", group="Temporal Tick"),
    node("GetHistoryATick", "variable_get", variable="HistoryA", group="Temporal Tick"),
    node("GetHistoryBTick", "variable_get", variable="HistoryB", group="Temporal Tick"),
    node("GetCoreMIDTick", "variable_get", variable="CoreMID", group="M2-B Fields"),
    node(
        "GetSmallBlurMIDTick",
        "variable_get",
        variable="SmallBlurMID",
        group="M2-B Fields",
    ),
    node(
        "GetLargeBlurMIDTick",
        "variable_get",
        variable="LargeBlurMID",
        group="M2-B Fields",
    ),
    node(
        "GetDensityMIDTick",
        "variable_get",
        variable="DensityMID",
        group="M2-B Fields",
    ),
    node(
        "GetNiagaraTick",
        "variable_get",
        variable="SSPRNiagara",
        group="Live Tuning",
    ),
    node(
        "GetSplatRadiusPx",
        "variable_get",
        variable="SplatRadiusPx",
        group="Live Tuning",
    ),
    node(
        "GetTrailTimeSeconds",
        "variable_get",
        variable="TrailTimeSeconds",
        group="Live Tuning",
    ),
    node(
        "GetMaxTrailPx",
        "variable_get",
        variable="MaxTrailPx",
        group="Live Tuning",
    ),
    node(
        "SetNiagaraSplatRadius",
        "function_call",
        **{
            "class": "NiagaraComponent",
            "function": "SetVariableFloat",
            "group": "Live Tuning",
        },
    ),
    node(
        "SetNiagaraTrailTime",
        "function_call",
        **{
            "class": "NiagaraComponent",
            "function": "SetVariableFloat",
            "group": "Live Tuning",
        },
    ),
    node(
        "SetNiagaraMaxTrail",
        "function_call",
        **{
            "class": "NiagaraComponent",
            "function": "SetVariableFloat",
            "group": "Live Tuning",
        },
    ),
    node(
        "GetSmallBlurRadiusPx",
        "variable_get",
        variable="SmallBlurRadiusPx",
        group="Live Tuning",
    ),
    node(
        "GetLargeBlurRadiusPx",
        "variable_get",
        variable="LargeBlurRadiusPx",
        group="Live Tuning",
    ),
    node(
        "GetCoreWeight",
        "variable_get",
        variable="CoreWeight",
        group="Live Tuning",
    ),
    node(
        "GetSmallBlurWeight",
        "variable_get",
        variable="SmallBlurWeight",
        group="Live Tuning",
    ),
    node(
        "GetLargeBlurWeight",
        "variable_get",
        variable="LargeBlurWeight",
        group="Live Tuning",
    ),
    node(
        "SetSmallBlurRadius",
        "function_call",
        **{
            "class": "MaterialInstanceDynamic",
            "function": "SetScalarParameterValue",
            "group": "Live Tuning",
        },
    ),
    node(
        "SetLargeBlurRadius",
        "function_call",
        **{
            "class": "MaterialInstanceDynamic",
            "function": "SetScalarParameterValue",
            "group": "Live Tuning",
        },
    ),
    node(
        "SetDensityCoreWeight",
        "function_call",
        **{
            "class": "MaterialInstanceDynamic",
            "function": "SetScalarParameterValue",
            "group": "Live Tuning",
        },
    ),
    node(
        "SetDensitySmallWeight",
        "function_call",
        **{
            "class": "MaterialInstanceDynamic",
            "function": "SetScalarParameterValue",
            "group": "Live Tuning",
        },
    ),
    node(
        "SetDensityLargeWeight",
        "function_call",
        **{
            "class": "MaterialInstanceDynamic",
            "function": "SetScalarParameterValue",
            "group": "Live Tuning",
        },
    ),
    node("GetCoreRTTick", "variable_get", variable="CoreRT", group="M2-B Fields"),
    node(
        "GetBlurSmallRTTick",
        "variable_get",
        variable="BlurSmallRT",
        group="M2-B Fields",
    ),
    node(
        "GetBlurLargeRTTick",
        "variable_get",
        variable="BlurLargeRT",
        group="M2-B Fields",
    ),
    node(
        "GetDensityRTTick",
        "variable_get",
        variable="DensityRT",
        group="M2-B Fields",
    ),
    node(
        "GetSmokeMIDTick",
        "variable_get",
        variable="SmokeMID",
        group="M2-C Resolve",
    ),
    node(
        "GetSmokeRTTick",
        "variable_get",
        variable="SmokeRT",
        group="M2-C Resolve",
    ),
    node(
        "GetSmokeCardPivotTick",
        "variable_get",
        variable="SmokeCardPivot",
        group="Smoke Card",
    ),
    node(
        "GetSmokeCardDistance",
        "variable_get",
        variable="SmokeCardDistance",
        group="Smoke Card",
    ),
    node(
        "ScaleSmokeCardForward",
        "function_call",
        **{
            "class": "KismetMathLibrary",
            "function": "Multiply_VectorFloat",
            "group": "Smoke Card",
        },
    ),
    node(
        "AddSmokeCardLocation",
        "function_call",
        **{
            "class": "KismetMathLibrary",
            "function": "Add_VectorVector",
            "group": "Smoke Card",
        },
    ),
    node(
        "SetSmokeCardTransform",
        "function_call",
        **{
            "class": "SceneComponent",
            "function": "K2_SetWorldLocationAndRotation",
            "group": "Smoke Card",
        },
    ),
    node("GetDecay", "variable_get", variable="DecayRate", group="Temporal Tick"),
    node(
        "GetHistoryValid",
        "variable_get",
        variable="HistoryValidValue",
        group="Temporal Tick",
    ),
    node(
        "GetReprojection",
        "variable_get",
        variable="ReprojectionValue",
        group="Temporal Tick",
    ),
]

nodes.extend(
    [
        node(
            "GetCameraManager",
            "function_call",
            **{
                "class": "GameplayStatics",
                "function": "GetPlayerCameraManager",
                "group": "Camera Reprojection",
            },
        ),
        node(
            "GetCameraLocation",
            "function_call",
            **{
                "class": "PlayerCameraManager",
                "function": "GetCameraLocation",
                "group": "Camera Reprojection",
            },
        ),
        node(
            "GetDynamicRepresentativeDepth",
            "function_call",
            **{
                "class": "Actor",
                "function": "GetDistanceTo",
                "group": "Camera Reprojection",
            },
        ),
        node(
            "GetCameraRotation",
            "function_call",
            **{
                "class": "PlayerCameraManager",
                "function": "GetCameraRotation",
                "group": "Camera Reprojection",
            },
        ),
        node(
            "GetCameraForward",
            "function_call",
            **{
                "class": "KismetMathLibrary",
                "function": "GetForwardVector",
                "group": "Camera Reprojection",
            },
        ),
        node(
            "GetCameraRight",
            "function_call",
            **{
                "class": "KismetMathLibrary",
                "function": "GetRightVector",
                "group": "Camera Reprojection",
            },
        ),
        node(
            "GetCameraUp",
            "function_call",
            **{
                "class": "KismetMathLibrary",
                "function": "GetUpVector",
                "group": "Camera Reprojection",
            },
        ),
        node(
            "GetPreviousCameraPosition",
            "variable_get",
            variable="PreviousCameraPosition",
            group="Camera Reprojection",
        ),
        node(
            "GetPreviousCameraForward",
            "variable_get",
            variable="PreviousCameraForward",
            group="Camera Reprojection",
        ),
        node(
            "GetPreviousCameraRight",
            "variable_get",
            variable="PreviousCameraRight",
            group="Camera Reprojection",
        ),
        node(
            "GetPreviousCameraUp",
            "variable_get",
            variable="PreviousCameraUp",
            group="Camera Reprojection",
        ),
        node(
            "GetCameraDataValid",
            "variable_get",
            variable="CameraDataValid",
            group="Camera Reprojection",
        ),
        node(
            "SetCameraDataValidParam",
            "function_call",
            **{
                "class": "MaterialInstanceDynamic",
                "function": "SetScalarParameterValue",
                "group": "Camera Reprojection",
            },
        ),
    ]
)

camera_vector_parameters = (
    ("CurrentCameraPosition", "GetCameraLocation", "ReturnValue"),
    ("CurrentCameraForward", "GetCameraForward", "ReturnValue"),
    ("CurrentCameraRight", "GetCameraRight", "ReturnValue"),
    ("CurrentCameraUp", "GetCameraUp", "ReturnValue"),
    (
        "PreviousCameraPosition",
        "GetPreviousCameraPosition",
        "PreviousCameraPosition",
    ),
    (
        "PreviousCameraForward",
        "GetPreviousCameraForward",
        "PreviousCameraForward",
    ),
    ("PreviousCameraRight", "GetPreviousCameraRight", "PreviousCameraRight"),
    ("PreviousCameraUp", "GetPreviousCameraUp", "PreviousCameraUp"),
)

for parameter_name, source_ref, source_pin in camera_vector_parameters:
    nodes.extend(
        [
            node(
                "Convert" + parameter_name,
                "function_call",
                **{
                    "class": "KismetMathLibrary",
                    "function": "Conv_VectorToLinearColor",
                    "group": "Camera Reprojection",
                },
            ),
            node(
                "Set" + parameter_name,
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetVectorParameterValue",
                    "group": "Camera Reprojection",
                },
            ),
        ]
    )


def append_history_path(prefix, write_a):
    history_read = "GetHistoryBTick" if write_a else "GetHistoryATick"
    history_read_pin = "HistoryB" if write_a else "HistoryA"
    history_write = "GetHistoryATick" if write_a else "GetHistoryBTick"
    history_write_pin = "HistoryA" if write_a else "HistoryB"

    nodes.extend(
        [
            node(
                prefix + "SetCurrent",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "SetHistory",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "SetDelta",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetScalarParameterValue",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "SetDecay",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetScalarParameterValue",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "SetDepth",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetScalarParameterValue",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "SetValid",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetScalarParameterValue",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "SetReprojection",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetScalarParameterValue",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "Draw",
                "function_call",
                **{
                    "class": "KismetRenderingLibrary",
                    "function": "DrawMaterialToRenderTarget",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "SetCoreSource",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "DrawCore",
                "function_call",
                **{
                    "class": "KismetRenderingLibrary",
                    "function": "DrawMaterialToRenderTarget",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "SetSmallSource",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "DrawSmall",
                "function_call",
                **{
                    "class": "KismetRenderingLibrary",
                    "function": "DrawMaterialToRenderTarget",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "SetLargeSource",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "DrawLarge",
                "function_call",
                **{
                    "class": "KismetRenderingLibrary",
                    "function": "DrawMaterialToRenderTarget",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "SetDensityCore",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "SetDensitySmall",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "SetDensityLarge",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "DrawDensity",
                "function_call",
                **{
                    "class": "KismetRenderingLibrary",
                    "function": "DrawMaterialToRenderTarget",
                    "group": prefix + " M2-B",
                },
            ),
            node(
                prefix + "ClearSmokeFrame",
                "function_call",
                **{
                    "class": "KismetRenderingLibrary",
                    "function": "ClearRenderTarget2D",
                    "group": prefix + " M2-C",
                },
            ),
            node(
                prefix + "SetSmokeDensity",
                "function_call",
                **{
                    "class": "MaterialInstanceDynamic",
                    "function": "SetTextureParameterValue",
                    "group": prefix + " M2-C",
                },
            ),
            node(
                prefix + "DrawSmoke",
                "function_call",
                **{
                    "class": "KismetRenderingLibrary",
                    "function": "DrawMaterialToRenderTarget",
                    "group": prefix + " M2-C",
                },
            ),
            node(
                prefix + "ClearCurrent",
                "function_call",
                **{
                    "class": "KismetRenderingLibrary",
                    "function": "ClearRenderTarget2D",
                    "group": prefix + " Path",
                },
            ),
            node(
                prefix + "SetLatest",
                "variable_set",
                variable="LatestHistory",
                group=prefix + " Path",
            ),
            node(
                prefix + "Toggle",
                "variable_set",
                variable="bWriteHistoryA",
                group=prefix + " Path",
            ),
            node(
                prefix + "Validate",
                "variable_set",
                variable="HistoryValidValue",
                group=prefix + " Path",
            ),
            node(
                prefix + "StorePreviousPosition",
                "variable_set",
                variable="PreviousCameraPosition",
                group=prefix + " Path",
            ),
            node(
                prefix + "StorePreviousForward",
                "variable_set",
                variable="PreviousCameraForward",
                group=prefix + " Path",
            ),
            node(
                prefix + "StorePreviousRight",
                "variable_set",
                variable="PreviousCameraRight",
                group=prefix + " Path",
            ),
            node(
                prefix + "StorePreviousUp",
                "variable_set",
                variable="PreviousCameraUp",
                group=prefix + " Path",
            ),
            node(
                prefix + "ValidateCamera",
                "variable_set",
                variable="CameraDataValid",
                group=prefix + " Path",
            ),
        ]
    )

    exec_refs = [
        prefix + "SetCurrent",
        prefix + "SetHistory",
        prefix + "SetDelta",
        prefix + "SetDecay",
        prefix + "SetDepth",
        prefix + "SetValid",
        prefix + "SetReprojection",
        prefix + "Draw",
        prefix + "SetCoreSource",
        prefix + "DrawCore",
        prefix + "SetSmallSource",
        prefix + "DrawSmall",
        prefix + "SetLargeSource",
        prefix + "DrawLarge",
        prefix + "SetDensityCore",
        prefix + "SetDensitySmall",
        prefix + "SetDensityLarge",
        prefix + "DrawDensity",
        prefix + "ClearSmokeFrame",
        prefix + "SetSmokeDensity",
        prefix + "DrawSmoke",
        prefix + "ClearCurrent",
        prefix + "SetLatest",
        prefix + "Toggle",
        prefix + "Validate",
        prefix + "StorePreviousPosition",
        prefix + "StorePreviousForward",
        prefix + "StorePreviousRight",
        prefix + "StorePreviousUp",
        prefix + "ValidateCamera",
    ]
    branch_pin = "then" if write_a else "else"
    connections.append(connection("BranchHistory." + branch_pin, exec_refs[0] + ".execute"))
    for left, right in zip(exec_refs, exec_refs[1:]):
        connections.append(connection(left + ".then", right + ".execute"))

    for target in (
        prefix + "SetCurrent",
        prefix + "SetHistory",
        prefix + "SetDelta",
        prefix + "SetDecay",
        prefix + "SetDepth",
        prefix + "SetValid",
        prefix + "SetReprojection",
    ):
        connections.append(connection("GetMIDTick.TemporalMID", target + ".self"))

    connections.extend(
        [
            connection(
                "GetCurrentTick.CurrentRT",
                prefix + "SetCurrent.Value",
            ),
            connection(
                history_read + "." + history_read_pin,
                prefix + "SetHistory.Value",
            ),
            connection("Tick.DeltaSeconds", prefix + "SetDelta.Value"),
            connection("GetDecay.DecayRate", prefix + "SetDecay.Value"),
            connection(
                "GetDynamicRepresentativeDepth.ReturnValue",
                prefix + "SetDepth.Value",
            ),
            connection(
                "GetHistoryValid.HistoryValidValue",
                prefix + "SetValid.Value",
            ),
            connection(
                "GetReprojection.ReprojectionValue",
                prefix + "SetReprojection.Value",
            ),
            connection(
                history_write + "." + history_write_pin,
                prefix + "Draw.TextureRenderTarget",
            ),
            connection("GetMIDTick.TemporalMID", prefix + "Draw.Material"),
            connection(
                "GetCoreMIDTick.CoreMID",
                prefix + "SetCoreSource.self",
            ),
            connection(
                history_write + "." + history_write_pin,
                prefix + "SetCoreSource.Value",
            ),
            connection(
                "GetCoreRTTick.CoreRT",
                prefix + "DrawCore.TextureRenderTarget",
            ),
            connection(
                "GetCoreMIDTick.CoreMID",
                prefix + "DrawCore.Material",
            ),
            connection(
                "GetSmallBlurMIDTick.SmallBlurMID",
                prefix + "SetSmallSource.self",
            ),
            connection(
                history_write + "." + history_write_pin,
                prefix + "SetSmallSource.Value",
            ),
            connection(
                "GetBlurSmallRTTick.BlurSmallRT",
                prefix + "DrawSmall.TextureRenderTarget",
            ),
            connection(
                "GetSmallBlurMIDTick.SmallBlurMID",
                prefix + "DrawSmall.Material",
            ),
            connection(
                "GetLargeBlurMIDTick.LargeBlurMID",
                prefix + "SetLargeSource.self",
            ),
            connection(
                "GetBlurSmallRTTick.BlurSmallRT",
                prefix + "SetLargeSource.Value",
            ),
            connection(
                "GetBlurLargeRTTick.BlurLargeRT",
                prefix + "DrawLarge.TextureRenderTarget",
            ),
            connection(
                "GetLargeBlurMIDTick.LargeBlurMID",
                prefix + "DrawLarge.Material",
            ),
            connection(
                "GetDensityMIDTick.DensityMID",
                prefix + "SetDensityCore.self",
            ),
            connection(
                "GetCoreRTTick.CoreRT",
                prefix + "SetDensityCore.Value",
            ),
            connection(
                "GetDensityMIDTick.DensityMID",
                prefix + "SetDensitySmall.self",
            ),
            connection(
                "GetBlurSmallRTTick.BlurSmallRT",
                prefix + "SetDensitySmall.Value",
            ),
            connection(
                "GetDensityMIDTick.DensityMID",
                prefix + "SetDensityLarge.self",
            ),
            connection(
                "GetBlurLargeRTTick.BlurLargeRT",
                prefix + "SetDensityLarge.Value",
            ),
            connection(
                "GetDensityRTTick.DensityRT",
                prefix + "DrawDensity.TextureRenderTarget",
            ),
            connection(
                "GetDensityMIDTick.DensityMID",
                prefix + "DrawDensity.Material",
            ),
            connection(
                "GetSmokeRTTick.SmokeRT",
                prefix + "ClearSmokeFrame.TextureRenderTarget",
            ),
            connection(
                "GetSmokeMIDTick.SmokeMID",
                prefix + "SetSmokeDensity.self",
            ),
            connection(
                "GetDensityRTTick.DensityRT",
                prefix + "SetSmokeDensity.Value",
            ),
            connection(
                "GetSmokeRTTick.SmokeRT",
                prefix + "DrawSmoke.TextureRenderTarget",
            ),
            connection(
                "GetSmokeMIDTick.SmokeMID",
                prefix + "DrawSmoke.Material",
            ),
            connection(
                "GetCurrentTick.CurrentRT",
                prefix + "ClearCurrent.TextureRenderTarget",
            ),
            connection(
                history_write + "." + history_write_pin,
                prefix + "SetLatest.LatestHistory",
            ),
            connection(
                "GetCameraLocation.ReturnValue",
                prefix + "StorePreviousPosition.PreviousCameraPosition",
            ),
            connection(
                "GetCameraForward.ReturnValue",
                prefix + "StorePreviousForward.PreviousCameraForward",
            ),
            connection(
                "GetCameraRight.ReturnValue",
                prefix + "StorePreviousRight.PreviousCameraRight",
            ),
            connection(
                "GetCameraUp.ReturnValue",
                prefix + "StorePreviousUp.PreviousCameraUp",
            ),
        ]
    )

    pin_defaults.extend(
        [
            default(prefix + "SetCurrent", "ParameterName", "CurrentTexture"),
            default(prefix + "SetHistory", "ParameterName", "HistoryTexture"),
            default(prefix + "SetDelta", "ParameterName", "DeltaSeconds"),
            default(prefix + "SetDecay", "ParameterName", "DecayRate"),
            default(
                prefix + "SetDepth",
                "ParameterName",
                "RepresentativeDepth",
            ),
            default(prefix + "SetValid", "ParameterName", "HistoryValid"),
            default(
                prefix + "SetReprojection",
                "ParameterName",
                "ReprojectionEnabled",
            ),
            default(
                prefix + "SetCoreSource",
                "ParameterName",
                "SourceTexture",
            ),
            default(
                prefix + "SetSmallSource",
                "ParameterName",
                "SourceTexture",
            ),
            default(
                prefix + "SetLargeSource",
                "ParameterName",
                "SourceTexture",
            ),
            default(
                prefix + "SetDensityCore",
                "ParameterName",
                "CoreTexture",
            ),
            default(
                prefix + "SetDensitySmall",
                "ParameterName",
                "SmallTexture",
            ),
            default(
                prefix + "SetDensityLarge",
                "ParameterName",
                "LargeTexture",
            ),
            default(
                prefix + "ClearSmokeFrame",
                "ClearColor",
                "(R=0.0,G=0.0,B=0.0,A=0.0)",
            ),
            default(
                prefix + "SetSmokeDensity",
                "ParameterName",
                "DensityTexture",
            ),
            default(
                prefix + "ClearCurrent",
                "ClearColor",
                "(R=0.0,G=0.0,B=0.0,A=0.0)",
            ),
            default(
                prefix + "Toggle",
                "bWriteHistoryA",
                "false" if write_a else "true",
            ),
            default(prefix + "Validate", "HistoryValidValue", "1.0"),
            default(prefix + "ValidateCamera", "CameraDataValid", "1.0"),
        ]
    )


connections = [
    connection("BeginPlay.then", "SetNiagaraRT.execute"),
    connection("GetNiagaraInit.SSPRNiagara", "SetNiagaraRT.self"),
    connection("GetCurrentInit.CurrentRT", "SetNiagaraRT.TextureRenderTarget"),
    connection("SetNiagaraRT.then", "AddTickPrerequisite.execute"),
    connection(
        "GetNiagaraInit.SSPRNiagara",
        "AddTickPrerequisite.PrerequisiteComponent",
    ),
    connection("AddTickPrerequisite.then", "CreateMID.execute"),
    connection("GetTemporalMaterial.TemporalMaterial", "CreateMID.Parent"),
    connection("CreateMID.then", "SetMID.execute"),
    connection("CreateMID.ReturnValue", "SetMID.TemporalMID"),
    connection("SetMID.then", "CreateCoreMID.execute"),
    connection("GetCoreMaterial.CoreMaterial", "CreateCoreMID.Parent"),
    connection("CreateCoreMID.then", "SetCoreMID.execute"),
    connection("CreateCoreMID.ReturnValue", "SetCoreMID.CoreMID"),
    connection("SetCoreMID.then", "CreateSmallBlurMID.execute"),
    connection(
        "GetSmallBlurMaterial.SmallBlurMaterial",
        "CreateSmallBlurMID.Parent",
    ),
    connection("CreateSmallBlurMID.then", "SetSmallBlurMID.execute"),
    connection(
        "CreateSmallBlurMID.ReturnValue",
        "SetSmallBlurMID.SmallBlurMID",
    ),
    connection("SetSmallBlurMID.then", "CreateLargeBlurMID.execute"),
    connection(
        "GetLargeBlurMaterial.LargeBlurMaterial",
        "CreateLargeBlurMID.Parent",
    ),
    connection("CreateLargeBlurMID.then", "SetLargeBlurMID.execute"),
    connection(
        "CreateLargeBlurMID.ReturnValue",
        "SetLargeBlurMID.LargeBlurMID",
    ),
    connection("SetLargeBlurMID.then", "CreateDensityMID.execute"),
    connection(
        "GetDensityMaterial.DensityMaterial",
        "CreateDensityMID.Parent",
    ),
    connection("CreateDensityMID.then", "SetDensityMID.execute"),
    connection("CreateDensityMID.ReturnValue", "SetDensityMID.DensityMID"),
    connection("SetDensityMID.then", "CreateSmokeMID.execute"),
    connection("GetSmokeMaterial.SmokeMaterial", "CreateSmokeMID.Parent"),
    connection("CreateSmokeMID.then", "SetSmokeMID.execute"),
    connection("CreateSmokeMID.ReturnValue", "SetSmokeMID.SmokeMID"),
    connection("SetSmokeMID.then", "SetSmokeCardMaterial.execute"),
    connection(
        "GetSmokeCardInit.SmokeCard",
        "SetSmokeCardMaterial.self",
    ),
    connection(
        "GetSmokeCardMaterialInit.SmokeCardMaterial",
        "SetSmokeCardMaterial.Material",
    ),
    connection(
        "SetSmokeCardMaterial.then",
        "ClearCurrentInit.execute",
    ),
    connection(
        "GetCurrentInit.CurrentRT",
        "ClearCurrentInit.TextureRenderTarget",
    ),
    connection("ClearCurrentInit.then", "ClearHistoryAInit.execute"),
    connection(
        "GetHistoryAInit.HistoryA",
        "ClearHistoryAInit.TextureRenderTarget",
    ),
    connection("ClearHistoryAInit.then", "ClearHistoryBInit.execute"),
    connection(
        "GetHistoryBInit.HistoryB",
        "ClearHistoryBInit.TextureRenderTarget",
    ),
    connection("ClearHistoryBInit.then", "ClearCoreInit.execute"),
    connection("GetCoreRTInit.CoreRT", "ClearCoreInit.TextureRenderTarget"),
    connection("ClearCoreInit.then", "ClearBlurSmallInit.execute"),
    connection(
        "GetBlurSmallRTInit.BlurSmallRT",
        "ClearBlurSmallInit.TextureRenderTarget",
    ),
    connection("ClearBlurSmallInit.then", "ClearBlurLargeInit.execute"),
    connection(
        "GetBlurLargeRTInit.BlurLargeRT",
        "ClearBlurLargeInit.TextureRenderTarget",
    ),
    connection("ClearBlurLargeInit.then", "ClearDensityInit.execute"),
    connection(
        "GetDensityRTInit.DensityRT",
        "ClearDensityInit.TextureRenderTarget",
    ),
    connection("ClearDensityInit.then", "ClearSmokeInit.execute"),
    connection(
        "GetSmokeRTInit.SmokeRT",
        "ClearSmokeInit.TextureRenderTarget",
    ),
    connection("ClearSmokeInit.then", "SetWriteAInit.execute"),
    connection("SetWriteAInit.then", "SetValidInit.execute"),
    connection("SetValidInit.then", "SetLatestInit.execute"),
    connection("GetHistoryAInit.HistoryA", "SetLatestInit.LatestHistory"),
    connection("SetLatestInit.then", "ActivateNiagara.execute"),
    connection("GetNiagaraInit.SSPRNiagara", "ActivateNiagara.self"),
    connection("ResetTemporalHistory.then", "ResetClearCurrent.execute"),
    connection(
        "GetCurrentInit.CurrentRT",
        "ResetClearCurrent.TextureRenderTarget",
    ),
    connection("ResetClearCurrent.then", "ResetClearHistoryA.execute"),
    connection(
        "GetHistoryAInit.HistoryA",
        "ResetClearHistoryA.TextureRenderTarget",
    ),
    connection("ResetClearHistoryA.then", "ResetClearHistoryB.execute"),
    connection(
        "GetHistoryBInit.HistoryB",
        "ResetClearHistoryB.TextureRenderTarget",
    ),
    connection("ResetClearHistoryB.then", "ResetClearCore.execute"),
    connection(
        "GetCoreRTInit.CoreRT",
        "ResetClearCore.TextureRenderTarget",
    ),
    connection("ResetClearCore.then", "ResetClearBlurSmall.execute"),
    connection(
        "GetBlurSmallRTInit.BlurSmallRT",
        "ResetClearBlurSmall.TextureRenderTarget",
    ),
    connection("ResetClearBlurSmall.then", "ResetClearBlurLarge.execute"),
    connection(
        "GetBlurLargeRTInit.BlurLargeRT",
        "ResetClearBlurLarge.TextureRenderTarget",
    ),
    connection("ResetClearBlurLarge.then", "ResetClearDensity.execute"),
    connection(
        "GetDensityRTInit.DensityRT",
        "ResetClearDensity.TextureRenderTarget",
    ),
    connection("ResetClearDensity.then", "ResetClearSmoke.execute"),
    connection(
        "GetSmokeRTInit.SmokeRT",
        "ResetClearSmoke.TextureRenderTarget",
    ),
    connection("ResetClearSmoke.then", "ResetWriteA.execute"),
    connection("ResetWriteA.then", "ResetHistoryValid.execute"),
    connection("ResetHistoryValid.then", "ResetCameraValid.execute"),
    connection("ResetCameraValid.then", "ResetLatestHistory.execute"),
    connection(
        "GetHistoryAInit.HistoryA",
        "ResetLatestHistory.LatestHistory",
    ),
    connection("ResetLatestHistory.then", "ResetNiagara.execute"),
    connection("GetNiagaraInit.SSPRNiagara", "ResetNiagara.self"),
    connection("GetWriteA.bWriteHistoryA", "BranchHistory.Condition"),
]

connections.extend(
    [
        connection(
            "GetCameraManager.ReturnValue",
            "GetCameraLocation.self",
        ),
        connection(
            "GetCameraManager.ReturnValue",
            "GetCameraRotation.self",
        ),
        connection(
            "GetCameraManager.ReturnValue",
            "GetDynamicRepresentativeDepth.OtherActor",
        ),
        connection(
            "GetCameraRotation.ReturnValue",
            "GetCameraForward.InRot",
        ),
        connection(
            "GetCameraRotation.ReturnValue",
            "GetCameraRight.InRot",
        ),
        connection(
            "GetCameraRotation.ReturnValue",
            "GetCameraUp.InRot",
        ),
        connection(
            "GetMIDTick.TemporalMID",
            "SetCameraDataValidParam.self",
        ),
        connection(
            "GetCameraDataValid.CameraDataValid",
            "SetCameraDataValidParam.Value",
        ),
        connection(
            "SetCameraDataValidParam.then",
            "SetNiagaraSplatRadius.execute",
        ),
        connection(
            "SetNiagaraSplatRadius.then",
            "SetNiagaraTrailTime.execute",
        ),
        connection(
            "SetNiagaraTrailTime.then",
            "SetNiagaraMaxTrail.execute",
        ),
        connection(
            "SetNiagaraMaxTrail.then",
            "SetSmallBlurRadius.execute",
        ),
        connection(
            "SetSmallBlurRadius.then",
            "SetLargeBlurRadius.execute",
        ),
        connection(
            "SetLargeBlurRadius.then",
            "SetDensityCoreWeight.execute",
        ),
        connection(
            "SetDensityCoreWeight.then",
            "SetDensitySmallWeight.execute",
        ),
        connection(
            "SetDensitySmallWeight.then",
            "SetDensityLargeWeight.execute",
        ),
        connection(
            "SetDensityLargeWeight.then",
            "SetSmokeCardTransform.execute",
        ),
        connection(
            "GetNiagaraTick.SSPRNiagara",
            "SetNiagaraSplatRadius.self",
        ),
        connection(
            "GetNiagaraTick.SSPRNiagara",
            "SetNiagaraTrailTime.self",
        ),
        connection(
            "GetNiagaraTick.SSPRNiagara",
            "SetNiagaraMaxTrail.self",
        ),
        connection(
            "GetSplatRadiusPx.SplatRadiusPx",
            "SetNiagaraSplatRadius.InValue",
        ),
        connection(
            "GetTrailTimeSeconds.TrailTimeSeconds",
            "SetNiagaraTrailTime.InValue",
        ),
        connection(
            "GetMaxTrailPx.MaxTrailPx",
            "SetNiagaraMaxTrail.InValue",
        ),
        connection(
            "GetSmallBlurMIDTick.SmallBlurMID",
            "SetSmallBlurRadius.self",
        ),
        connection(
            "GetSmallBlurRadiusPx.SmallBlurRadiusPx",
            "SetSmallBlurRadius.Value",
        ),
        connection(
            "GetLargeBlurMIDTick.LargeBlurMID",
            "SetLargeBlurRadius.self",
        ),
        connection(
            "GetLargeBlurRadiusPx.LargeBlurRadiusPx",
            "SetLargeBlurRadius.Value",
        ),
        connection(
            "GetDensityMIDTick.DensityMID",
            "SetDensityCoreWeight.self",
        ),
        connection(
            "GetCoreWeight.CoreWeight",
            "SetDensityCoreWeight.Value",
        ),
        connection(
            "GetDensityMIDTick.DensityMID",
            "SetDensitySmallWeight.self",
        ),
        connection(
            "GetSmallBlurWeight.SmallBlurWeight",
            "SetDensitySmallWeight.Value",
        ),
        connection(
            "GetDensityMIDTick.DensityMID",
            "SetDensityLargeWeight.self",
        ),
        connection(
            "GetLargeBlurWeight.LargeBlurWeight",
            "SetDensityLargeWeight.Value",
        ),
        connection(
            "GetCameraForward.ReturnValue",
            "ScaleSmokeCardForward.A",
        ),
        connection(
            "GetSmokeCardDistance.SmokeCardDistance",
            "ScaleSmokeCardForward.B",
        ),
        connection(
            "GetCameraLocation.ReturnValue",
            "AddSmokeCardLocation.A",
        ),
        connection(
            "ScaleSmokeCardForward.ReturnValue",
            "AddSmokeCardLocation.B",
        ),
        connection(
            "GetSmokeCardPivotTick.SmokeCardPivot",
            "SetSmokeCardTransform.self",
        ),
        connection(
            "AddSmokeCardLocation.ReturnValue",
            "SetSmokeCardTransform.NewLocation",
        ),
        connection(
            "GetCameraRotation.ReturnValue",
            "SetSmokeCardTransform.NewRotation",
        ),
        connection(
            "SetSmokeCardTransform.then",
            "BranchHistory.execute",
        ),
    ]
)

camera_set_refs = []
for parameter_name, source_ref, source_pin in camera_vector_parameters:
    convert_ref = "Convert" + parameter_name
    set_ref = "Set" + parameter_name
    camera_set_refs.append(set_ref)
    connections.extend(
        [
            connection(
                source_ref + "." + source_pin,
                convert_ref + ".InVec",
            ),
            connection(
                convert_ref + ".ReturnValue",
                set_ref + ".Value",
            ),
            connection(
                "GetMIDTick.TemporalMID",
                set_ref + ".self",
            ),
        ]
    )

connections.append(connection("Tick.then", camera_set_refs[0] + ".execute"))
for left, right in zip(camera_set_refs, camera_set_refs[1:]):
    connections.append(connection(left + ".then", right + ".execute"))
connections.append(
    connection(
        camera_set_refs[-1] + ".then",
        "SetCameraDataValidParam.execute",
    )
)

pin_defaults = [
    default("SetNiagaraRT", "InVariableName", "User.OccupancyRTParam"),
    default("ActivateNiagara", "bReset", "true"),
    default("SetSmokeCardMaterial", "ElementIndex", "0"),
    default("SetSmokeCardTransform", "bSweep", "false"),
    default("SetSmokeCardTransform", "bTeleport", "true"),
    default(
        "ClearCurrentInit",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ClearHistoryAInit",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ClearHistoryBInit",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ClearCoreInit",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ClearBlurSmallInit",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ClearBlurLargeInit",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ClearDensityInit",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ClearSmokeInit",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default("SetWriteAInit", "bWriteHistoryA", "true"),
    default("SetValidInit", "HistoryValidValue", "0.0"),
    default(
        "ResetClearCurrent",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ResetClearHistoryA",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ResetClearHistoryB",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ResetClearCore",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ResetClearBlurSmall",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ResetClearBlurLarge",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ResetClearDensity",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default(
        "ResetClearSmoke",
        "ClearColor",
        "(R=0.0,G=0.0,B=0.0,A=0.0)",
    ),
    default("ResetWriteA", "bWriteHistoryA", "true"),
    default("ResetHistoryValid", "HistoryValidValue", "0.0"),
    default("ResetCameraValid", "CameraDataValid", "0.0"),
    default("GetCameraManager", "PlayerIndex", "0"),
    default(
        "SetCameraDataValidParam",
        "ParameterName",
        "CameraDataValid",
    ),
    default(
        "SetNiagaraSplatRadius",
        "InVariableName",
        "User.SSPR_RadiusPx",
    ),
    default(
        "SetNiagaraTrailTime",
        "InVariableName",
        "User.SSPR_TrailTime",
    ),
    default(
        "SetNiagaraMaxTrail",
        "InVariableName",
        "User.SSPR_MaxTrailPx",
    ),
    default("SetSmallBlurRadius", "ParameterName", "RadiusPx"),
    default("SetLargeBlurRadius", "ParameterName", "RadiusPx"),
    default("SetDensityCoreWeight", "ParameterName", "CoreWeight"),
    default(
        "SetDensitySmallWeight",
        "ParameterName",
        "SmallBlurWeight",
    ),
    default(
        "SetDensityLargeWeight",
        "ParameterName",
        "LargeBlurWeight",
    ),
]

for parameter_name, _, _ in camera_vector_parameters:
    pin_defaults.append(
        default(
            "Set" + parameter_name,
            "ParameterName",
            parameter_name,
        )
    )

append_history_path("WriteA", True)
append_history_path("WriteB", False)

build_result = service.build_graph(
    BP,
    GRAPH,
    nodes,
    connections,
    pin_defaults,
    True,
    True,
)

if isinstance(build_result, tuple):
    success_flag = bool(build_result[0])
    detail = build_result[-1]
else:
    success_flag = bool(build_result)
    detail = build_result

detail_dict = (
    detail.to_dict()
    if hasattr(detail, "to_dict")
    else {"repr": repr(detail)}
)
saved = bool(unreal.EditorAssetLibrary.save_asset(BP, False))
result = {
    "removedNodes": len(removed),
    "success": success_flag,
    "detail": detail_dict,
    "saved": saved,
    "requestedNodes": len(nodes),
    "requestedConnections": len(connections),
    "requestedDefaults": len(pin_defaults),
}
print("M2A_BP_BUILD=" + json.dumps(result, sort_keys=True, default=str))
if not success_flag or not saved:
    raise RuntimeError("M2-A Blueprint graph build failed: " + repr(result))
