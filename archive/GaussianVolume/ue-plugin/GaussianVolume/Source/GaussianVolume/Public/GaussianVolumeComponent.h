// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GaussianVolumeTypes.h"
#include "GaussianVolumeComponent.generated.h"

class AGaussianVolumeActor;
class ADirectionalLight;
class ASkyLight;
class UGaussianVolumeWorldSubsystem;

namespace GaussianVolumeLighting
{
	inline float ResolveAtmosphereSunVisibility(float DirectionTowardLightZ)
	{
		// Fade through the first ~3 degrees above the horizon; never mirror sunlight below it.
		return FMath::Clamp(DirectionTowardLightZ / 0.05f, 0.0f, 1.0f);
	}
}

UENUM(BlueprintType)
enum class EGaussianVolumeDebugView : uint8
{
	Final,
	Primitive,
	OpticalDepth,
	Transmittance,
	CandidateCount,
	LightTransmittance,
};

/** A single Gaussian volume primitive (CPU-side editable representation). */
USTRUCT(BlueprintType)
struct FGaussianVolumePrimitive
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume")
	FVector Center = FVector::ZeroVector;

	/** Per-axis std dev (local coords), matches mvp/gaussian_volume.py `scale`. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume")
	FVector Scale = FVector(50.0, 50.0, 50.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume")
	FRotator Rotation = FRotator::ZeroRotator;

	/** Peak extinction coefficient (density), matches `sigma_t`. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume")
	float SigmaT = 1.0f;

	/** Local-space Gabor angular frequency. Zero keeps the primitive Gaussian. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume", meta = (ClampMin = "0.0"))
	float Omega = 0.0f;

	/** Single-scatter albedo. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume")
	FLinearColor Albedo = FLinearColor::White;

	/** Additive emission integrated through the same volume density. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume", meta = (ClampMin = "0.0"))
	float Emission = 0.0f;

	/** Offline optical depth toward the positive/negative local asset axes. */
	UPROPERTY()
	FVector3f PositiveLightTau = FVector3f::ZeroVector;

	UPROPERTY()
	FVector3f NegativeLightTau = FVector3f::ZeroVector;
};

/**
 * Holds Gaussian cloud data and manages the SceneViewExtension lifecycle.
 * Place this on an Actor in the level to enable GaussianVolume rendering.
 */
UCLASS(ClassGroup=(Rendering), meta=(BlueprintSpawnableComponent))
class GAUSSIANVOLUME_API UGaussianVolumeComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UGaussianVolumeComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void OnRegister() override;
	virtual void OnUnregister() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** CPU-side Gaussian primitives. Edit in the Details panel, or fill programmatically from a VDB converter later. */
	UPROPERTY()
	TArray<FGaussianVolumePrimitive> Gaussians;

	/** If Gaussians is empty at BeginPlay, add one default primitive at the component location. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume")
	bool bUseDebugDefaultGaussianIfEmpty = true;

	/** Toggle rendering on/off. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume")
	bool bEnableRendering = true;

	/** Scales extinction without regenerating the source data. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Rendering", meta = (ClampMin = "0.0", UIMin = "0.0", UIMax = "10.0"))
	float DensityMultiplier = 0.416f;

	/** Remaps normalized extinction; values below 1 lift low and mid densities while preserving the peak. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Rendering", meta = (ClampMin = "0.01", UIMin = "0.1", UIMax = "2.0"))
	float DensityGamma = 1.515627f;

	/** Minimum retained boundary-ray optical-depth proxy. Zero restores fixed 3-sigma support. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Rendering", meta = (ClampMin = "0.0", UIMin = "0.000001", UIMax = "0.001"))
	float SupportTauMin = 0.0f;

	/**
	 * Extra translated copies of this cloud. Offsets are in world axes relative
	 * to the owning Actor; all copies share one GPU primitive buffer.
	 * Restricted to uniform-appearance clouds so the high-count lighting path
	 * remains exact.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "GaussianVolume|Instances")
	TArray<FVector> AdditionalInstanceOffsets;

	/** Selects 30K/10K/4K-style data by projected volume size before the GPU upload. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|LOD")
	bool bEnableScreenSizeLod = false;

	/** Actor whose serialized Gaussians provide the medium-detail tier. Actor refs avoid inline expansion of DefaultToInstanced components. */
	UPROPERTY(EditInstanceOnly, Category = "GaussianVolume|LOD", meta = (EditCondition = "bEnableScreenSizeLod"))
	TObjectPtr<AGaussianVolumeActor> MediumLodSourceActor = nullptr;

	/** Actor whose serialized Gaussians provide the low-detail tier. Its transform is ignored. */
	UPROPERTY(EditInstanceOnly, Category = "GaussianVolume|LOD", meta = (EditCondition = "bEnableScreenSizeLod"))
	TObjectPtr<AGaussianVolumeActor> LowLodSourceActor = nullptr;

	/** High detail is used above this horizontal normalized screen radius. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|LOD", meta = (EditCondition = "bEnableScreenSizeLod", ClampMin = "0.01", UIMin = "0.05", UIMax = "1.0"))
	float HighLodMinScreenRadius = 0.35f;

	/** Medium detail is used above this radius; below it the low tier is used. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|LOD", meta = (EditCondition = "bEnableScreenSizeLod", ClampMin = "0.005", UIMin = "0.01", UIMax = "0.5"))
	float MediumLodMinScreenRadius = 0.12f;

	/** Relative half-width of the smooth blend band around both LOD thresholds. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|LOD", meta = (EditCondition = "bEnableScreenSizeLod", ClampMin = "0.0", ClampMax = "0.5"))
	float LodHysteresis = 0.15f;

	// --- Lighting Parameters (Phase 3) ---

	/** Read direction/color/intensity from the explicitly assigned level lights. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting")
	bool bUseSceneLights = true;

	UPROPERTY(EditInstanceOnly, Category = "GaussianVolume|Lighting", meta = (EditCondition = "bUseSceneLights"))
	TObjectPtr<ADirectionalLight> DirectionalLightActor = nullptr;

	UPROPERTY(EditInstanceOnly, Category = "GaussianVolume|Lighting", meta = (EditCondition = "bUseSceneLights"))
	TObjectPtr<ASkyLight> SkyLightActor = nullptr;

	/** Converts directional-light scene units to this shader's radiance scale. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting", meta = (EditCondition = "bUseSceneLights", ClampMin = "0.0"))
	float DirectionalLightIntensityScale = 0.5f;

	/** Converts sky-light scene units to this shader's ambient scale. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting", meta = (EditCondition = "bUseSceneLights", ClampMin = "0.0"))
	float SkyLightIntensityScale = 0.1f;

	/** Direction toward the dominant light source (normalized). */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting", meta = (MakeEditWidget = true))
	FVector LightDirection = FVector(0.5, -0.5, 0.707);

	/** Light color * intensity. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting")
	FLinearColor LightColor = FLinearColor(1.0f, 0.95f, 0.85f, 1.0f);

	/** Ambient color (fake multi-scatter). */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting")
	FLinearColor AmbientColor = FLinearColor(0.1f, 0.15f, 0.2f, 1.0f);

	/** Powder effect strength (0 = off, 0.5 = default). */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float PowderFactor = 0.5f;

	/** Calibration for baked directional self-shadow optical depth. */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting", meta = (ClampMin = "0.0", UIMin = "0.0", UIMax = "4.0"))
	float DirectionalShadowDensityScale = 1.0f;

	/** Maximum ray distance for integration (world units). */
	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Lighting", meta = (ClampMin = "100.0"))
	float MaxRayDistance = 100000.0f;

	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Rendering")
	bool bUseSceneDepth = true;

	UPROPERTY(EditAnywhere, Category = "GaussianVolume|Rendering")
	EGaussianVolumeDebugView DebugView = EGaussianVolumeDebugView::Final;

	/** Re-pack Gaussians into the StructuredBuffer layout and push to the render thread. Call after editing Gaussians at runtime. */
	UFUNCTION(BlueprintCallable, Category = "GaussianVolume")
	void PushGaussianDataToRenderThread();

	/** Samples the same Gaussian density field used by the renderer. */
	UFUNCTION(BlueprintPure, Category = "GaussianVolume")
	float SampleDensityAtWorldPosition(FVector WorldPosition) const;

#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

private:
	UGaussianVolumeWorldSubsystem* GetGaussianSubsystem() const;
	bool ShouldRender() const;
	float GetPeakSigmaT(TConstArrayView<FGaussianVolumePrimitive> Source) const;
	float RemapSigmaT(float SigmaT, float PeakSigmaT) const;
	void PackPrimitives(
		TConstArrayView<FGaussianVolumePrimitive> Source,
		const FTransform& OwnerTransform,
		TArray<GaussianVolumeGPU::FPackedPrimitive>& OutPacked,
		FBox* OutBounds = nullptr) const;

	void PushLightingToRenderThread();
	FTransform LastOwnerTransform;
	bool bLastShouldRender = true;
};
