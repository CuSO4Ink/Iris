// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GaussianVolumeTypes.h"
#include "SceneViewExtension.h"
#include "RHIGPUReadback.h"
#include "RHIResources.h"
#include "RenderGraphResources.h"

struct FPostProcessMaterialInputs;
struct FScreenPassTexture;

class FGaussianVolumeSceneViewExtension : public FWorldSceneViewExtension
{
public:
	FGaussianVolumeSceneViewExtension(const FAutoRegister& AutoReg, UWorld* InWorld);

	/** Subscribe to a post-processing pass so we can composite AFTER tonemapping,
	 *  when the final on-screen color is available and writing it actually shows up. */
	virtual void SubscribeToPostProcessingPass(
		EPostProcessingPass Pass,
		const FSceneView& InView,
		FPostProcessingPassDelegateArray& InOutPassCallbacks,
		bool bIsPassEnabled) override;

	/** The actual composite callback invoked by the post-process pass. */
	FScreenPassTexture PostProcessCallback_RenderThread(
		FRDGBuilder& GraphBuilder,
		const FSceneView& InView,
		const FPostProcessMaterialInputs& Inputs);

	void UpdateGaussianData_GameThread(
		TArray<GaussianVolumeGPU::FPackedPrimitive> HighPackedData,
		TArray<GaussianVolumeGPU::FPackedPrimitive> MediumPackedData,
		TArray<GaussianVolumeGPU::FPackedPrimitive> LowPackedData,
		TArray<GaussianVolumeGPU::FPackedInstance> HighInstances,
		TArray<GaussianVolumeGPU::FPackedInstance> MediumInstances,
		TArray<GaussianVolumeGPU::FPackedInstance> LowInstances,
		FVector BoundsCenter,
		float BoundsRadius,
		bool bEnableScreenSizeLod,
		float HighMinScreenRadius,
		float MediumMinScreenRadius,
		float LodHysteresis);

	/** Game-thread entry to update lighting parameters (pushed to render thread). */
	void UpdateLighting_GameThread(
		FVector LightDir, FLinearColor LightColor, FLinearColor AmbientColor,
		float PowderFactor, float MaxRayDistance, bool bUseSceneDepth, uint32 DebugView);

	void UpdateNanoVdbData_GameThread(
		TArray<uint32> GridWords,
		const FMatrix44f& WorldToNanoLocal,
		FLinearColor Albedo,
		float DensityScale,
		float StepSizeVoxels,
		uint32 MaxSteps,
		bool bUseSceneDepth);

private:
	// Render-thread-only Gaussian data
	TArray<GaussianVolumeGPU::FPackedPrimitive> PackedGaussianData_RT[3];
	TArray<GaussianVolumeGPU::FPackedInstance> PackedInstanceData_RT[3];
	FVector4f UniformAppearance_RT[3] = {
		FVector4f(1, 1, 1, 0), FVector4f(1, 1, 1, 0), FVector4f(1, 1, 1, 0)};
	bool bUniformAppearance_RT[3] = {false, false, false};
	bool bDirectionalLightTau_RT[3] = {false, false, false};
	FVector LodBoundsCenter_RT = FVector::ZeroVector;
	float LodBoundsRadius_RT = 0.0f;
	float HighLodMinScreenRadius_RT = 0.35f;
	float MediumLodMinScreenRadius_RT = 0.12f;
	float LodHysteresis_RT = 0.15f;
	bool bEnableScreenSizeLod_RT = false;

	// Render-thread-only lighting state
	FVector4f LightDir_RT       = FVector4f(0.5f, -0.5f, 0.707f, 0.0f);  // default: upper-left
	FVector4f LightColor_RT     = FVector4f(1.0f, 0.95f, 0.85f, 1.0f);   // warm sunlight
	FVector4f AmbientColor_RT   = FVector4f(0.1f, 0.15f, 0.2f, 1.0f);    // cool ambient
	float PowderFactor_RT       = 0.5f;
	float MaxRayDistance_RT     = 1e5f;
	uint32 bUseSceneDepth_RT    = 1;
	uint32 DebugView_RT         = 0;
	TRefCountPtr<FRDGPooledBuffer> LightTauPooled_RT[3];
	bool bLightTauDirty_RT[3] = {true, true, true};

	TArray<uint32> NanoVdbWords_RT;
	FMatrix44f NanoWorldToLocal_RT = FMatrix44f::Identity;
	FVector4f NanoAlbedo_RT = FVector4f(1, 1, 1, 1);
	float NanoDensityScale_RT = 1.0f;
	float NanoStepSizeVoxels_RT = 0.75f;
	uint32 NanoMaxSteps_RT = 1024;
	uint32 bNanoUseSceneDepth_RT = 1;

	TUniquePtr<FRHIGPUBufferReadback> CandidateStatsReadback_RT;
	bool bCandidateStatsReadbackPending_RT = false;
	bool bCandidateStatsRequestConsumed_RT = false;
	uint32 CandidateStatsDelayFrames_RT = 0;
	int32 CandidateStatsNumGaussians_RT = 0;
	int32 CandidateStatsNumInstances_RT = 0;
	int32 CandidateStatsVirtualGaussians_RT = 0;
	int32 CandidateStatsLightTauElements_RT = 0;
	int32 CandidateStatsInstanceBufferElements_RT = 0;
	FIntPoint CandidateStatsResolution_RT = FIntPoint::ZeroValue;
	FVector CandidateStatsViewOrigin_RT = FVector::ZeroVector;
};
