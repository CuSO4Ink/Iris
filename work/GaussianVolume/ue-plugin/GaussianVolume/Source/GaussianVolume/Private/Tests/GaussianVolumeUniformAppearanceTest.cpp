// Copyright 2026 Violina. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "GaussianVolumeActor.h"
#include "GaussianVolumeComponent.h"
#include "GaussianVolumeTypes.h"
#include "Misc/AutomationTest.h"
#include "UObject/UnrealType.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FGaussianVolumeUniformAppearanceTest,
	"GaussianVolume.UniformAppearance", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGaussianVolumeUniformAppearanceTest::RunTest(const FString& Parameters)
{
	const FVector Center(123.25, -456.5, 789.75);
	const FVector Scale(1.25, 2.5, 4.0);
	const FQuat Rotation(FRotator(15.0, 25.0, 35.0));
	const FLinearColor Appearance(0.25f, 0.5f, 0.75f);
	constexpr float SigmaT = 1.5f;
	constexpr float Emission = 0.125f;
	const FVector3f PositiveLightTau(1.0f, 2.0f, 3.0f);
	const FVector3f NegativeLightTau(4.0f, 5.0f, 6.0f);
	TArray<GaussianVolumeGPU::FPackedPrimitive> Packed;
	GaussianVolumeGPU::PackPrimitive(
		Center, Scale, Rotation, SigmaT, 1.25f, Appearance, Emission, Packed, 0.0f,
		PositiveLightTau, NegativeLightTau);
	GaussianVolumeGPU::PackPrimitive(FVector(1), FVector(1), FQuat::Identity, 2.0f, 0.0f, Appearance, Emission, Packed);
	TestEqual(TEXT("packed primitive is exactly 48 bytes"), sizeof(GaussianVolumeGPU::FPackedPrimitive), SIZE_T(48));
	TestEqual(TEXT("one structured element per primitive"), Packed.Num(), 2);
	TestTrue(TEXT("FP32 center survives packing"),
		FMath::IsNearlyEqual(FMath::AsFloat(Packed[0].Data0.X), static_cast<float>(Center.X))
		&& FMath::IsNearlyEqual(FMath::AsFloat(Packed[0].Data0.Y), static_cast<float>(Center.Y))
		&& FMath::IsNearlyEqual(FMath::AsFloat(Packed[0].Data0.Z), static_cast<float>(Center.Z)));
	const FVector2f SigmaSupport = GaussianVolumeGPU::UnpackHalf2(Packed[0].Data0.W);
	const FVector2f ScaleXY = GaussianVolumeGPU::UnpackHalf2(Packed[0].Data1.X);
	const FVector2f ScaleZEmission = GaussianVolumeGPU::UnpackHalf2(Packed[0].Data1.Y);
	TestTrue(TEXT("FP16 density, support, scale, and emission decode"),
		FMath::IsNearlyEqual(SigmaSupport.X, SigmaT, 1e-3f)
		&& FMath::IsNearlyEqual(SigmaSupport.Y, 3.0f, 1e-3f)
		&& FMath::IsNearlyEqual(ScaleXY.X, static_cast<float>(Scale.X), 1e-3f)
		&& FMath::IsNearlyEqual(ScaleXY.Y, static_cast<float>(Scale.Y), 1e-3f)
		&& FMath::IsNearlyEqual(ScaleZEmission.X, static_cast<float>(Scale.Z), 1e-3f)
		&& FMath::IsNearlyEqual(ScaleZEmission.Y, Emission, 1e-3f));
	TestTrue(TEXT("SNORM8 quaternion stays aligned"),
		FMath::Abs(Rotation.GetNormalized() | GaussianVolumeGPU::UnpackSnorm8x4(Packed[0].Data1.Z)) > 0.999f);
	TestTrue(TEXT("UNORM8 appearance stays within one code value"),
		GaussianVolumeGPU::GetAppearance(Packed[0]).Equals(
			FVector4f(Appearance.R, Appearance.G, Appearance.B, Emission), 1.0f / 255.0f));
	TestTrue(TEXT("FP32 Gabor frequency survives packing"),
		FMath::IsNearlyEqual(FMath::AsFloat(Packed[0].Data2.X), 1.25f));
	TestTrue(TEXT("six directional optical depths survive FP16 packing"),
		GaussianVolumeGPU::UnpackHalf2(Packed[0].Data2.Y).Equals(FVector2f(1.0f, 4.0f), 1e-3f)
		&& GaussianVolumeGPU::UnpackHalf2(Packed[0].Data2.Z).Equals(FVector2f(2.0f, 5.0f), 1e-3f)
		&& GaussianVolumeGPU::UnpackHalf2(Packed[0].Data2.W).Equals(FVector2f(3.0f, 6.0f), 1e-3f));
	TestTrue(TEXT("directional optical depth is detected"), GaussianVolumeGPU::HasDirectionalLightTau(Packed));
	const FVector InstanceOffset(100.25, -200.5, 300.75);
	const GaussianVolumeGPU::FPackedInstance Instance =
		GaussianVolumeGPU::PackInstance(InstanceOffset, 17u, 9944u, Rotation);
	TestEqual(TEXT("packed shared instance is exactly 32 bytes"),
		sizeof(GaussianVolumeGPU::FPackedInstance), SIZE_T(32));
	TestTrue(TEXT("instance offset and primitive range survive packing"),
		FMath::IsNearlyEqual(FMath::AsFloat(Instance.Data0.X), static_cast<float>(InstanceOffset.X))
		&& FMath::IsNearlyEqual(FMath::AsFloat(Instance.Data0.Y), static_cast<float>(InstanceOffset.Y))
		&& FMath::IsNearlyEqual(FMath::AsFloat(Instance.Data0.Z), static_cast<float>(InstanceOffset.Z))
		&& Instance.Data0.W == 17u
		&& Instance.Data1.X == 9944u);
	TestTrue(TEXT("instance light-basis rotation survives packing"),
		FMath::Abs(Rotation.GetNormalized() | GaussianVolumeGPU::UnpackSnorm8x4(Instance.Data1.Y)) > 0.999f);
	TestEqual(TEXT("atmosphere sun below the horizon contributes no direct light"),
		GaussianVolumeLighting::ResolveAtmosphereSunVisibility(-0.5f), 0.0f);
	TestEqual(TEXT("atmosphere sun reaches full direct light above the horizon fade"),
		GaussianVolumeLighting::ResolveAtmosphereSunVisibility(0.05f), 1.0f);
	TestTrue(TEXT("matching albedo and emission are uniform"), GaussianVolumeGPU::HasUniformAppearance(Packed));
	Packed.Last().Data1.W ^= 1u;
	TestFalse(TEXT("different albedo disables the fast path"), GaussianVolumeGPU::HasUniformAppearance(Packed));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FGaussianVolumeAdaptiveSupportTest,
	"GaussianVolume.AdaptiveSupport", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGaussianVolumeAdaptiveSupportTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("zero threshold restores fixed support"),
		GaussianVolumeGPU::ResolveSupportSigma(1.0f, 1.0f, 0.0f), 3.0f);
	TestEqual(TEXT("sub-threshold primitive is culled"),
		GaussianVolumeGPU::ResolveSupportSigma(1e-6f, 1.0f, 1e-5f), 0.0f);
	const float Adaptive = GaussianVolumeGPU::ResolveSupportSigma(1e-4f, 1.0f, 1e-5f);
	TestTrue(TEXT("low optical depth shrinks support"), Adaptive > 0.0f && Adaptive < 3.0f);
	TestEqual(TEXT("high optical depth never expands past fixed support"),
		GaussianVolumeGPU::ResolveSupportSigma(1.0f, 1.0f, 1e-5f), 3.0f);
	float MinSlope = 0.0f;
	float MaxSlope = 0.0f;
	TestTrue(TEXT("projected unit sphere has finite bounds"),
		GaussianVolumeGPU::ProjectEllipsoidAxisBounds(
			0.0f, 5.0f, 1.0f, 0.0f, 1.0f, 1.0f, MinSlope, MaxSlope));
	TestTrue(TEXT("unit sphere slope matches tangent"),
		FMath::IsNearlyEqual(MaxSlope, 1.0f / FMath::Sqrt(24.0f), 1e-5f)
		&& FMath::IsNearlyEqual(MinSlope, -MaxSlope, 1e-5f));
	float ThinMin = 0.0f;
	float ThinMax = 0.0f;
	TestTrue(TEXT("anisotropic projected bound is valid"),
		GaussianVolumeGPU::ProjectEllipsoidAxisBounds(
			0.0f, 5.0f, 0.25f, 0.0f, 1.0f, 1.0f, ThinMin, ThinMax));
	TestTrue(TEXT("thin ellipsoid projects tighter than support sphere"), ThinMax < MaxSlope);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FGaussianVolumeScreenSizeLodTest,
	"GaussianVolume.ScreenSizeLod", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGaussianVolumeScreenSizeLodTest::RunTest(const FString& Parameters)
{
	constexpr float High = 0.35f;
	constexpr float Medium = 0.12f;
	constexpr float BlendBand = 0.15f;
	const GaussianVolumeGPU::FScreenSizeLodBlend HighOnly = GaussianVolumeGPU::SelectScreenSizeLodBlend(0.5f, High, Medium, BlendBand);
	const GaussianVolumeGPU::FScreenSizeLodBlend HighMedium = GaussianVolumeGPU::SelectScreenSizeLodBlend(High, High, Medium, BlendBand);
	const GaussianVolumeGPU::FScreenSizeLodBlend MediumOnly = GaussianVolumeGPU::SelectScreenSizeLodBlend(0.2f, High, Medium, BlendBand);
	const GaussianVolumeGPU::FScreenSizeLodBlend MediumLow = GaussianVolumeGPU::SelectScreenSizeLodBlend(Medium, High, Medium, BlendBand);
	const GaussianVolumeGPU::FScreenSizeLodBlend LowOnly = GaussianVolumeGPU::SelectScreenSizeLodBlend(0.05f, High, Medium, BlendBand);
	TestTrue(TEXT("large screen radius uses high only"), HighOnly.LodA == 0 && HighOnly.LodB == 0);
	TestTrue(TEXT("high threshold blends high to medium"), HighMedium.LodA == 0 && HighMedium.LodB == 1 && FMath::IsNearlyEqual(HighMedium.Alpha, 0.5f));
	TestTrue(TEXT("between bands uses medium only"), MediumOnly.LodA == 1 && MediumOnly.LodB == 1);
	TestTrue(TEXT("medium threshold blends medium to low"), MediumLow.LodA == 1 && MediumLow.LodB == 2 && FMath::IsNearlyEqual(MediumLow.Alpha, 0.5f));
	TestTrue(TEXT("small screen radius uses low only"), LowOnly.LodA == 2 && LowOnly.LodB == 2);
	TestEqual(TEXT("zero requests exact candidate pool capacity"),
		GaussianVolumeGPU::ResolveCandidatePoolCapacity(0, 2040, 30000), 61200000u);
	TestEqual(TEXT("positive request applies total pool cap"),
		GaussianVolumeGPU::ResolveCandidatePoolCapacity(512 * 1024, 2040, 30000), 524288u);
	TestEqual(TEXT("pool cap cannot exceed exact tile matrix"),
		GaussianVolumeGPU::ResolveCandidatePoolCapacity(100000, 10, 100), 1000u);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FGaussianVolumeLodSourcePropertyTest,
	"GaussianVolume.LodSourceProperty", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGaussianVolumeLodSourcePropertyTest::RunTest(const FString& Parameters)
{
	const FObjectPropertyBase* Medium = FindFProperty<FObjectPropertyBase>(
		UGaussianVolumeComponent::StaticClass(), GET_MEMBER_NAME_CHECKED(UGaussianVolumeComponent, MediumLodSourceActor));
	const FObjectPropertyBase* Low = FindFProperty<FObjectPropertyBase>(
		UGaussianVolumeComponent::StaticClass(), GET_MEMBER_NAME_CHECKED(UGaussianVolumeComponent, LowLodSourceActor));
	TestNotNull(TEXT("medium LOD source property"), Medium);
	TestNotNull(TEXT("low LOD source property"), Low);
	if (Medium && Low)
	{
		TestEqual(TEXT("medium source uses an actor picker"), Medium->PropertyClass.Get(), AGaussianVolumeActor::StaticClass());
		TestEqual(TEXT("low source uses an actor picker"), Low->PropertyClass.Get(), AGaussianVolumeActor::StaticClass());
		TestFalse(TEXT("medium source is not inline-instanced"), Medium->HasAnyPropertyFlags(CPF_InstancedReference));
		TestFalse(TEXT("low source is not inline-instanced"), Low->HasAnyPropertyFlags(CPF_InstancedReference));
	}
	return true;
}

#endif
