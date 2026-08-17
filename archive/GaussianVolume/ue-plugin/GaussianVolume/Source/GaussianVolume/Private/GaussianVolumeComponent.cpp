// Copyright 2026 Violina. All Rights Reserved.

#include "GaussianVolumeComponent.h"
#include "GaussianVolumeActor.h"
#include "GaussianVolumeSubsystem.h"
#include "GaussianVolumeTypes.h"
#include "Components/SceneComponent.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"

UGaussianVolumeWorldSubsystem* UGaussianVolumeComponent::GetGaussianSubsystem() const
{
	const UWorld* World = GetWorld();
	return World ? World->GetSubsystem<UGaussianVolumeWorldSubsystem>() : nullptr;
}

bool UGaussianVolumeComponent::ShouldRender() const
{
	const AActor* Owner = GetOwner();
	if (!bEnableRendering || (Owner && Owner->IsHidden()))
	{
		return false;
	}
	if (Owner && Owner->GetRootComponent() && !Owner->GetRootComponent()->IsVisible())
	{
		return false;
	}
#if WITH_EDITOR
	return !Owner || !Owner->IsHiddenEd();
#else
	return true;
#endif
}

float UGaussianVolumeComponent::GetPeakSigmaT(TConstArrayView<FGaussianVolumePrimitive> Source) const
{
	float PeakSigmaT = 0.0f;
	for (const FGaussianVolumePrimitive& G : Source)
	{
		if (FMath::IsFinite(G.SigmaT))
		{
			PeakSigmaT = FMath::Max(PeakSigmaT, FMath::Abs(G.SigmaT));
		}
	}
	return PeakSigmaT;
}

void UGaussianVolumeComponent::PackPrimitives(
	TConstArrayView<FGaussianVolumePrimitive> Source,
	const FTransform& OwnerTransform,
	TArray<GaussianVolumeGPU::FPackedPrimitive>& OutPacked,
	FBox* OutBounds) const
{
	OutPacked.Reserve(Source.Num());
	const FVector OwnerScale = OwnerTransform.GetScale3D().GetAbs();
	const float PeakSigmaT = GetPeakSigmaT(Source);
	for (const FGaussianVolumePrimitive& G : Source)
	{
		if (G.Center.ContainsNaN() || G.Scale.ContainsNaN() || !FMath::IsFinite(G.SigmaT)
			|| !FMath::IsFinite(G.Omega) || !FMath::IsFinite(G.Emission))
		{
			UE_LOG(LogTemp, Warning, TEXT("GaussianVolume: skipped non-finite primitive"));
			continue;
		}

		const FVector SafeScale = (G.Scale.GetAbs() * OwnerScale).ComponentMax(FVector(0.01));
		const FVector WorldCenter = OwnerTransform.TransformPosition(G.Center);
		const FQuat WorldRotation = (OwnerTransform.GetRotation() * FQuat(G.Rotation)).GetNormalized();
		const float BoundRadius = GaussianVolumeGPU::PackPrimitive(
			WorldCenter, SafeScale, WorldRotation, RemapSigmaT(G.SigmaT, PeakSigmaT), FMath::Max(G.Omega, 0.0f), G.Albedo,
			FMath::Max(G.Emission, 0.0f), OutPacked, SupportTauMin,
			G.PositiveLightTau * FMath::Max(DirectionalShadowDensityScale * DensityMultiplier, 0.0f),
			G.NegativeLightTau * FMath::Max(DirectionalShadowDensityScale * DensityMultiplier, 0.0f));

		if (OutBounds && BoundRadius > 0.0f)
		{
			const FVector BoundExtent(BoundRadius);
			*OutBounds += WorldCenter - BoundExtent;
			*OutBounds += WorldCenter + BoundExtent;
		}
	}
}

float UGaussianVolumeComponent::RemapSigmaT(float SigmaT, float PeakSigmaT) const
{
	if (PeakSigmaT <= 0.0f)
	{
		return 0.0f;
	}
	const float Sign = SigmaT < 0.0f ? -1.0f : 1.0f;
	return Sign * FMath::Pow(FMath::Clamp(FMath::Abs(SigmaT) / PeakSigmaT, 0.0f, 1.0f), FMath::Max(DensityGamma, 0.01f))
		* PeakSigmaT * FMath::Max(DensityMultiplier, 0.0f);
}

UGaussianVolumeComponent::UGaussianVolumeComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.0f;
	bTickInEditor = true;
}

void UGaussianVolumeComponent::BeginPlay()
{
	Super::BeginPlay();

	PushGaussianDataToRenderThread();
	PushLightingToRenderThread();
	LastOwnerTransform = GetOwner() ? GetOwner()->GetActorTransform() : FTransform::Identity;
}

void UGaussianVolumeComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const bool bShouldRender = ShouldRender();
	if (bShouldRender != bLastShouldRender)
	{
		PushGaussianDataToRenderThread();
	}
	if (GetOwner() && !GetOwner()->GetActorTransform().Equals(LastOwnerTransform))
	{
		LastOwnerTransform = GetOwner()->GetActorTransform();
		PushGaussianDataToRenderThread();
	}
	if (bUseSceneLights && (DirectionalLightActor || SkyLightActor))
	{
		// ponytail: poll editor lights; replace with dirty notifications only if this game-thread update becomes measurable.
		PushLightingToRenderThread();
	}
}

void UGaussianVolumeComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UGaussianVolumeWorldSubsystem* Subsystem = GetGaussianSubsystem())
	{
		Subsystem->UnregisterComponent(this);
	}
	Super::EndPlay(EndPlayReason);
}

void UGaussianVolumeComponent::OnUnregister()
{
	// Editor deletion / RerunConstructionScripts does NOT call EndPlay, so drop our
	// primitives from the shared renderer here too — otherwise a deleted Actor's Gaussians
	// keep rendering (they stay in the subsystem's merged buffer).
	if (UGaussianVolumeWorldSubsystem* Subsystem = GetGaussianSubsystem())
	{
		Subsystem->UnregisterComponent(this);
	}
	Super::OnUnregister();
}

void UGaussianVolumeComponent::OnRegister()
{
	Super::OnRegister();

	if (ShouldRender() && GetWorld())
	{
		if (bUseDebugDefaultGaussianIfEmpty && Gaussians.Num() == 0)
		{
			FGaussianVolumePrimitive Debug;
			Debug.Center = FVector::ZeroVector;
			Debug.Scale = FVector(300.0, 300.0, 300.0);
			Debug.SigmaT = 2.0f;
			Debug.Albedo = FLinearColor(0.9f, 0.6f, 0.2f, 1.0f);  // warm orange, highly visible
			Gaussians.Add(Debug);
		}

		if (UGaussianVolumeWorldSubsystem* Subsystem = GetGaussianSubsystem())
		{
			Subsystem->RegisterComponent(this);
		}
		LastOwnerTransform = GetOwner() ? GetOwner()->GetActorTransform() : FTransform::Identity;
		PushGaussianDataToRenderThread();
		PushLightingToRenderThread();
	}
}

void UGaussianVolumeComponent::PushGaussianDataToRenderThread()
{
	UGaussianVolumeWorldSubsystem* Subsystem = GetGaussianSubsystem();
	if (!Subsystem)
	{
		return;
	}
	bLastShouldRender = ShouldRender();
	if (!bLastShouldRender)
	{
		Subsystem->UnregisterComponent(this);
		return;
	}
	Subsystem->RegisterComponent(this);

	const FTransform OwnerTransform = GetOwner() ? GetOwner()->GetActorTransform() : FTransform::Identity;
	TArray<GaussianVolumeGPU::FPackedPrimitive> HighPacked;
	TArray<GaussianVolumeGPU::FPackedPrimitive> MediumPacked;
	TArray<GaussianVolumeGPU::FPackedPrimitive> LowPacked;
	FBox WorldBounds(ForceInit);
	PackPrimitives(Gaussians, OwnerTransform, HighPacked, &WorldBounds);

	const UGaussianVolumeComponent* MediumLodComponent = MediumLodSourceActor ? MediumLodSourceActor->GaussianVolumeComponent.Get() : nullptr;
	const UGaussianVolumeComponent* LowLodComponent = LowLodSourceActor ? LowLodSourceActor->GaussianVolumeComponent.Get() : nullptr;
	if (bEnableScreenSizeLod && MediumLodComponent && MediumLodComponent != this)
	{
		PackPrimitives(MediumLodComponent->Gaussians, OwnerTransform, MediumPacked);
	}
	if (bEnableScreenSizeLod && LowLodComponent && LowLodComponent != this)
	{
		PackPrimitives(LowLodComponent->Gaussians, OwnerTransform, LowPacked);
	}

	Subsystem->UpdateComponentData(
		this, MoveTemp(HighPacked), MoveTemp(MediumPacked), MoveTemp(LowPacked), WorldBounds,
		AdditionalInstanceOffsets, OwnerTransform.GetRotation(),
		bEnableScreenSizeLod, HighLodMinScreenRadius, MediumLodMinScreenRadius, LodHysteresis);
}

void UGaussianVolumeComponent::PushLightingToRenderThread()
{
	UGaussianVolumeWorldSubsystem* Subsystem = GetGaussianSubsystem();
	if (!Subsystem)
	{
		return;
	}
	FVector EffectiveDirection = LightDirection;
	FLinearColor EffectiveLight = LightColor;
	FLinearColor EffectiveAmbient = AmbientColor;
	if (bUseSceneLights && DirectionalLightActor && DirectionalLightActor->GetLightComponent())
	{
		const UDirectionalLightComponent* DirectionalLight =
			CastChecked<UDirectionalLightComponent>(DirectionalLightActor->GetLightComponent());
		EffectiveDirection = -DirectionalLightActor->GetActorForwardVector();
		float DirectVisibility = DirectionalLight->GetVisibleFlag() && DirectionalLight->bAffectsWorld ? 1.0f : 0.0f;
		if (DirectionalLight->IsUsedAsAtmosphereSunLight())
		{
			DirectVisibility *= GaussianVolumeLighting::ResolveAtmosphereSunVisibility(EffectiveDirection.Z);
		}
		EffectiveLight *= DirectionalLight->GetColoredLightBrightness()
			* FMath::Max(DirectionalLightIntensityScale, 0.0f) * DirectVisibility;
	}
	if (bUseSceneLights && SkyLightActor && SkyLightActor->GetLightComponent())
	{
		const USkyLightComponent* Sky = SkyLightActor->GetLightComponent();
		EffectiveAmbient *= Sky->GetLightColor() * Sky->Intensity * FMath::Max(SkyLightIntensityScale, 0.0f);
	}
	Subsystem->UpdateLighting(
		EffectiveDirection.GetSafeNormal(UE_SMALL_NUMBER, FVector(0.5, -0.5, 0.707)), EffectiveLight, EffectiveAmbient,
		PowderFactor, MaxRayDistance, bUseSceneDepth, static_cast<uint32>(DebugView));
}

float UGaussianVolumeComponent::SampleDensityAtWorldPosition(FVector WorldPosition) const
{
	const FTransform OwnerTransform = GetOwner() ? GetOwner()->GetActorTransform() : FTransform::Identity;
	const FVector LocalPosition = OwnerTransform.InverseTransformPosition(WorldPosition);
	float DensitySum = 0.0f;
	const float PeakSigmaT = GetPeakSigmaT(Gaussians);
	for (const FGaussianVolumePrimitive& G : Gaussians)
	{
		const FVector SafeScale = G.Scale.GetAbs().ComponentMax(FVector(0.01));
		const FVector Delta = FQuat(G.Rotation).UnrotateVector(LocalPosition - G.Center);
		const FVector Q = Delta / SafeScale;
		DensitySum += RemapSigmaT(G.SigmaT, PeakSigmaT) * FMath::Exp(-0.5f * Q.SizeSquared())
			* FMath::Cos(FMath::Max(G.Omega, 0.0f) * (Q.X + Q.Y + Q.Z));
	}
	return FMath::Max(DensitySum, 0.0f);
}

#if WITH_EDITOR
void UGaussianVolumeComponent::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);
	PushGaussianDataToRenderThread();
	PushLightingToRenderThread();
}
#endif
