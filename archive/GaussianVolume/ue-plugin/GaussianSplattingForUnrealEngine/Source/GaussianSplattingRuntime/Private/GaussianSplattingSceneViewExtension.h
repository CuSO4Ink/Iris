#pragma once

#include "GaussianSplatting7DTypes.h"
#include "RenderGraphResources.h"
#include "SceneViewExtension.h"

struct FPostProcessMaterialInputs;
struct FScreenPassTexture;

class FGaussianSplattingSceneViewExtension final : public FWorldSceneViewExtension
{
public:
	FGaussianSplattingSceneViewExtension(const FAutoRegister& AutoReg, UWorld* InWorld);

	virtual void SubscribeToPostProcessingPass(
		EPostProcessingPass Pass,
		const FSceneView& InView,
		FPostProcessingPassDelegateArray& InOutPassCallbacks,
		bool bIsPassEnabled) override;

	void UpdateData_GameThread(TArray<FVector4f> RawData);
	void UpdateParameters_GameThread(
		const GaussianSplatting7DRGS::FSourceParameters& Parameters);

private:
	FScreenPassTexture PostProcessCallback_RenderThread(
		FRDGBuilder& GraphBuilder,
		const FSceneView& InView,
		const FPostProcessMaterialInputs& Inputs);

	TArray<FVector4f> RawData_RT;
	TRefCountPtr<FRDGPooledBuffer> RawDataPooled_RT;
	GaussianSplatting7DRGS::FSourceParameters Parameters_RT;
	uint32 PointCount_RT = 0;
};
