#pragma once

#include "CoreMinimal.h"

namespace GaussianSplatting7DRGS
{
	static constexpr uint32 InputStrideFloat4 = 20;
	static constexpr uint32 SlicedStrideFloat4 = 4;

	struct FSourceParameters
	{
		FMatrix44f LocalToWorld = FMatrix44f::Identity;
		FVector3f LocalCenterOffset = FVector3f::ZeroVector;
		FVector3f ConditionDirection = FVector3f(0.0f, 0.0f, 1.0f);
		FVector3f LightDirectionWS = FVector3f(0.0f, 0.0f, 1.0f);
		FVector3f LightColor = FVector3f(8.0f, 8.0f, 8.0f);
		FVector3f AmbientLightColor = FVector3f::ZeroVector;
		FVector3f SourceWorldPosition = FVector3f::ZeroVector;
		float CurrentTime = 0.0f;
		float OpacityMultiplier = 1.0f;
		float OpacityPower = 1.0f;
		float PhaseG = 0.6f;
		float PhaseG2 = -0.2f;
		float PhaseBlend = 0.2f;
		float NubisEccentricity = 0.6f;
		float NubisSilverIntensity = 1.0f;
		float NubisSilverSpread = 0.2f;
		float PhaseIntensity = 1.0f;
		float DepthSoftFadeUU = 10.0f;
		uint32 TViewSHDegree = 3;
		uint32 PhaseMode = 0;
		uint32 DepthTestMode = 2;
		uint32 bDualSH = 1;
	};
}
