// Copyright 2026 Violina. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "GaussianVolumeComponent.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FGaussianVolumeDensityCurveTest,
	"GaussianVolume.DensityCurve", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGaussianVolumeDensityCurveTest::RunTest(const FString& Parameters)
{
	UGaussianVolumeComponent* Component = NewObject<UGaussianVolumeComponent>();
	Component->DensityMultiplier = 3.0f;
	Component->DensityGamma = 0.5f;
	Component->Gaussians.AddDefaulted(2);
	Component->Gaussians[0].SigmaT = 0.01f;
	Component->Gaussians[1].SigmaT = 0.04f;
	TestTrue(TEXT("normalized gamma preserves the peak and lifts lower density"),
		FMath::IsNearlyEqual(Component->SampleDensityAtWorldPosition(FVector::ZeroVector), 0.18f, 1.e-6f));
	Component->Gaussians[0].Omega = UE_PI;
	Component->Gaussians[0].SigmaT = -0.01f;
	TestTrue(TEXT("signed Gabor residual is evaluated and final density stays physical"),
		Component->SampleDensityAtWorldPosition(FVector::ZeroVector) >= 0.0f);
	return true;
}

#endif
