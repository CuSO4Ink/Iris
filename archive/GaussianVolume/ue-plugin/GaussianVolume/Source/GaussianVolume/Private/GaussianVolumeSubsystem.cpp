// Copyright 2026 Violina. All Rights Reserved.

#include "GaussianVolumeSubsystem.h"
#include "GaussianVolumeComponent.h"
#include "NanoVdbVolumeComponent.h"
#include "GaussianVolumeSceneViewExtension.h"
#include "GaussianVolumeTypes.h"
#include "SceneViewExtension.h"
#include "Engine/World.h"
#include "RenderingThread.h"

void UGaussianVolumeWorldSubsystem::Deinitialize()
{
	// Update commands capture the world-owned extension. Finish them before map teardown
	// releases the extension (especially important for rapid commandlet map swaps).
	FlushRenderingCommands();
	SceneViewExtension.Reset();
	ComponentData.Empty();
	NanoComponent.Reset();
	Super::Deinitialize();
}

void UGaussianVolumeWorldSubsystem::EnsureSceneViewExtension()
{
	if (!SceneViewExtension.IsValid() && GetWorld())
	{
		SceneViewExtension = FSceneViewExtensions::NewExtension<FGaussianVolumeSceneViewExtension>(GetWorld());
	}
}

void UGaussianVolumeWorldSubsystem::RegisterComponent(UGaussianVolumeComponent* Component)
{
	if (!Component)
	{
		return;
	}
	EnsureSceneViewExtension();
	// Ensure a slot exists even before data is pushed (empty until UpdateComponentData).
	ComponentData.FindOrAdd(Component);
}

void UGaussianVolumeWorldSubsystem::UnregisterComponent(UGaussianVolumeComponent* Component)
{
	if (ComponentData.Remove(Component) > 0)
	{
		RebuildMergedBuffer();
	}
}

void UGaussianVolumeWorldSubsystem::UpdateComponentData(
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
	float LodHysteresis)
{
	if (!Component)
	{
		return;
	}
	EnsureSceneViewExtension();
	FComponentRenderData& Data = ComponentData.FindOrAdd(Component);
	Data.High = MoveTemp(HighPacked);
	Data.Medium = MoveTemp(MediumPacked);
	Data.Low = MoveTemp(LowPacked);
	Data.WorldBounds = WorldBounds;
	Data.LightBasisRotation = LightBasisRotation.GetNormalized();
	Data.AdditionalInstanceOffsets.Reset();
	if (Data.High.Num() > 4096 && GaussianVolumeGPU::HasUniformAppearance(Data.High))
	{
		for (const FVector& Offset : AdditionalInstanceOffsets)
		{
			if (!Offset.ContainsNaN())
			{
				Data.AdditionalInstanceOffsets.Add(Offset);
			}
		}
	}
	else if (!AdditionalInstanceOffsets.IsEmpty())
	{
		UE_LOG(LogTemp, Warning,
			TEXT("GaussianVolume: shared translated instances require a >4K uniform-appearance cloud; offsets ignored"));
	}
	Data.bEnableScreenSizeLod = bEnableScreenSizeLod && Data.Medium.Num() > 0 && Data.Low.Num() > 0 && WorldBounds.IsValid;
	Data.HighMinScreenRadius = HighMinScreenRadius;
	Data.MediumMinScreenRadius = MediumMinScreenRadius;
	Data.LodHysteresis = LodHysteresis;
	RebuildMergedBuffer();
}

void UGaussianVolumeWorldSubsystem::RebuildMergedBuffer()
{
	if (!SceneViewExtension.IsValid())
	{
		return;
	}

	int32 HighTotal = 0;
	int32 MediumTotal = 0;
	int32 LowTotal = 0;
	for (const TPair<TWeakObjectPtr<UGaussianVolumeComponent>, FComponentRenderData>& Pair : ComponentData)
	{
		HighTotal += Pair.Value.High.Num();
		MediumTotal += Pair.Value.Medium.Num() > 0 ? Pair.Value.Medium.Num() : Pair.Value.High.Num();
		LowTotal += Pair.Value.Low.Num() > 0
			? Pair.Value.Low.Num()
			: (Pair.Value.Medium.Num() > 0 ? Pair.Value.Medium.Num() : Pair.Value.High.Num());
	}

	TArray<GaussianVolumeGPU::FPackedPrimitive> HighMerged;
	TArray<GaussianVolumeGPU::FPackedPrimitive> MediumMerged;
	TArray<GaussianVolumeGPU::FPackedPrimitive> LowMerged;
	TArray<GaussianVolumeGPU::FPackedInstance> HighInstances;
	TArray<GaussianVolumeGPU::FPackedInstance> MediumInstances;
	TArray<GaussianVolumeGPU::FPackedInstance> LowInstances;
	HighMerged.Reserve(HighTotal);
	MediumMerged.Reserve(MediumTotal);
	LowMerged.Reserve(LowTotal);
	FBox LodBounds(ForceInit);
	bool bEnableScreenSizeLod = false;
	float HighMinScreenRadius = 0.35f;
	float MediumMinScreenRadius = 0.12f;
	float LodHysteresis = 0.15f;
	for (auto It = ComponentData.CreateIterator(); It; ++It)
	{
		if (!It.Key().IsValid())
		{
			It.RemoveCurrent();  // prune components destroyed without an explicit unregister
			continue;
		}

		const FComponentRenderData& Data = It.Value();
		const uint32 HighOffset = static_cast<uint32>(HighMerged.Num());
		const uint32 MediumOffset = static_cast<uint32>(MediumMerged.Num());
		const uint32 LowOffset = static_cast<uint32>(LowMerged.Num());
		const TArray<GaussianVolumeGPU::FPackedPrimitive>& MediumSource =
			Data.Medium.Num() > 0 ? Data.Medium : Data.High;
		const TArray<GaussianVolumeGPU::FPackedPrimitive>& LowSource =
			Data.Low.Num() > 0 ? Data.Low : MediumSource;
		HighMerged.Append(Data.High);
		MediumMerged.Append(MediumSource);
		LowMerged.Append(LowSource);
		auto AddInstance = [&](const FVector& Offset)
		{
			HighInstances.Add(GaussianVolumeGPU::PackInstance(
				Offset, HighOffset, static_cast<uint32>(Data.High.Num()), Data.LightBasisRotation));
			MediumInstances.Add(GaussianVolumeGPU::PackInstance(
				Offset, MediumOffset, static_cast<uint32>(MediumSource.Num()), Data.LightBasisRotation));
			LowInstances.Add(GaussianVolumeGPU::PackInstance(
				Offset, LowOffset, static_cast<uint32>(LowSource.Num()), Data.LightBasisRotation));
			if (Data.WorldBounds.IsValid)
			{
				LodBounds += Data.WorldBounds.ShiftBy(Offset);
			}
		};
		AddInstance(FVector::ZeroVector);
		for (const FVector& Offset : Data.AdditionalInstanceOffsets)
		{
			AddInstance(Offset);
		}
		if (Data.bEnableScreenSizeLod)
		{
			bEnableScreenSizeLod = true;
			HighMinScreenRadius = Data.HighMinScreenRadius;
			MediumMinScreenRadius = Data.MediumMinScreenRadius;
			LodHysteresis = Data.LodHysteresis;
		}
	}

	const FVector BoundsCenter = LodBounds.IsValid ? LodBounds.GetCenter() : FVector::ZeroVector;
	const float BoundsRadius = LodBounds.IsValid ? static_cast<float>(LodBounds.GetExtent().Size()) : 0.0f;
	SceneViewExtension->UpdateGaussianData_GameThread(
		MoveTemp(HighMerged), MoveTemp(MediumMerged), MoveTemp(LowMerged),
		MoveTemp(HighInstances), MoveTemp(MediumInstances), MoveTemp(LowInstances),
		BoundsCenter, BoundsRadius, bEnableScreenSizeLod,
		HighMinScreenRadius, MediumMinScreenRadius, LodHysteresis);
}

void UGaussianVolumeWorldSubsystem::UpdateLighting(
	FVector LightDir, FLinearColor LightColor, FLinearColor AmbientColor,
	float PowderFactor, float MaxRayDistance, bool bUseSceneDepth, uint32 DebugView)
{
	EnsureSceneViewExtension();
	if (SceneViewExtension.IsValid())
	{
		SceneViewExtension->UpdateLighting_GameThread(
			LightDir, LightColor, AmbientColor, PowderFactor, MaxRayDistance, bUseSceneDepth, DebugView);
	}
}

void UGaussianVolumeWorldSubsystem::RegisterNanoComponent(UNanoVdbVolumeComponent* Component)
{
	if (!Component)
	{
		return;
	}
	EnsureSceneViewExtension();
	NanoComponent = Component;
}

void UGaussianVolumeWorldSubsystem::UnregisterNanoComponent(UNanoVdbVolumeComponent* Component)
{
	if (NanoComponent.Get() != Component)
	{
		return;
	}
	NanoComponent.Reset();
	if (SceneViewExtension.IsValid())
	{
		SceneViewExtension->UpdateNanoVdbData_GameThread(
			TArray<uint32>(), FMatrix44f::Identity, FLinearColor::White,
			0.0f, 1.0f, 64u, false);
	}
}

void UGaussianVolumeWorldSubsystem::UpdateNanoComponentData(
	UNanoVdbVolumeComponent* Component,
	TArray<uint32>&& GridWords,
	const FMatrix44f& WorldToNanoLocal,
	FLinearColor Albedo,
	float DensityScale,
	float StepSizeVoxels,
	uint32 MaxSteps,
	bool bUseSceneDepth)
{
	if (!Component)
	{
		return;
	}
	RegisterNanoComponent(Component);
	SceneViewExtension->UpdateNanoVdbData_GameThread(
		MoveTemp(GridWords), WorldToNanoLocal, Albedo,
		DensityScale, StepSizeVoxels, MaxSteps, bUseSceneDepth);
}
