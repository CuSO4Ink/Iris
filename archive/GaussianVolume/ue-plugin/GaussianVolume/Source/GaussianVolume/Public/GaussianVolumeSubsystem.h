// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GaussianVolumeTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "GaussianVolumeSubsystem.generated.h"

class FGaussianVolumeSceneViewExtension;
class UGaussianVolumeComponent;
class UNanoVdbVolumeComponent;

/**
 * One shared renderer per world.
 *
 * Each UGaussianVolumeComponent registers here instead of creating its own
 * SceneViewExtension. The subsystem owns a single SVE and merges every registered
 * component's packed primitives into ONE StructuredBuffer / ONE composite pass, so
 * primitives from different Actors occlude each other correctly (the shader's per-ray
 * t_star ordering resolves front-to-back across the merged set). Per-Actor appearance
 * (albedo / sigma_t / emission / transform) is preserved because it is baked into each
 * primitive before merging; only the pass-global lighting is shared (last-writer-wins).
 */
UCLASS()
class GAUSSIANVOLUME_API UGaussianVolumeWorldSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Deinitialize() override;

	/** Register / unregister a component (idempotent). Unregister prunes its primitives. */
	void RegisterComponent(UGaussianVolumeComponent* Component);
	void UnregisterComponent(UGaussianVolumeComponent* Component);

	/** Store one component's packed 32-byte LOD tiers and rebuild the merged buffers. */
	void UpdateComponentData(
		UGaussianVolumeComponent* Component,
		TArray<GaussianVolumeGPU::FPackedPrimitive>&& HighPacked,
		TArray<GaussianVolumeGPU::FPackedPrimitive>&& MediumPacked,
		TArray<GaussianVolumeGPU::FPackedPrimitive>&& LowPacked,
		const FBox& WorldBounds,
		TConstArrayView<FVector> AdditionalInstanceOffsets,
		const FQuat& LightBasisRotation,
		bool bEnableScreenSizeLod,
		float HighMinScreenRadius,
		float MediumMinScreenRadius,
		float LodHysteresis);

	/** Forward pass-global lighting to the shared SVE. */
	void UpdateLighting(
		FVector LightDir, FLinearColor LightColor, FLinearColor AmbientColor,
		float PowderFactor, float MaxRayDistance, bool bUseSceneDepth, uint32 DebugView);

	void RegisterNanoComponent(UNanoVdbVolumeComponent* Component);
	void UnregisterNanoComponent(UNanoVdbVolumeComponent* Component);
	void UpdateNanoComponentData(
		UNanoVdbVolumeComponent* Component,
		TArray<uint32>&& GridWords,
		const FMatrix44f& WorldToNanoLocal,
		FLinearColor Albedo,
		float DensityScale,
		float StepSizeVoxels,
		uint32 MaxSteps,
		bool bUseSceneDepth);

private:
	void EnsureSceneViewExtension();
	void RebuildMergedBuffer();

	TSharedPtr<FGaussianVolumeSceneViewExtension, ESPMode::ThreadSafe> SceneViewExtension;

	struct FComponentRenderData
	{
		TArray<GaussianVolumeGPU::FPackedPrimitive> High;
		TArray<GaussianVolumeGPU::FPackedPrimitive> Medium;
		TArray<GaussianVolumeGPU::FPackedPrimitive> Low;
		FBox WorldBounds = FBox(ForceInit);
		TArray<FVector> AdditionalInstanceOffsets;
		FQuat LightBasisRotation = FQuat::Identity;
		bool bEnableScreenSizeLod = false;
		float HighMinScreenRadius = 0.35f;
		float MediumMinScreenRadius = 0.12f;
		float LodHysteresis = 0.15f;
	};

	/** Per-component packed primitive data, keyed weakly so dead components self-prune. */
	TMap<TWeakObjectPtr<UGaussianVolumeComponent>, FComponentRenderData> ComponentData;
	TWeakObjectPtr<UNanoVdbVolumeComponent> NanoComponent;
};
