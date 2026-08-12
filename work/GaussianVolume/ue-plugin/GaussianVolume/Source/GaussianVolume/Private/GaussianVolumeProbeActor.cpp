// Copyright 2026 Violina. All Rights Reserved.

#include "GaussianVolumeProbeActor.h"
#include "GaussianVolumeActor.h"
#include "GaussianVolumeComponent.h"
#include "Components/PointLightComponent.h"

AGaussianVolumeProbeActor::AGaussianVolumeProbeActor()
{
	PrimaryActorTick.bCanEverTick = false;
	PointLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("DensityDrivenLight"));
	RootComponent = PointLight;
	// Movable: this light is moved AND has its intensity changed every Tick. A Static/
	// Stationary light gets its data cached by GPUScene, which then asserts the cached
	// data never changes ("GPU Scene Lights is stale" ensure). Movable opts out of that.
	PointLight->SetMobility(EComponentMobility::Movable);
	PointLight->SetAttenuationRadius(400.0f);
	PointLight->SetLightColor(FLinearColor(0.1f, 0.8f, 1.0f));
}

void AGaussianVolumeProbeActor::BeginPlay()
{
	Super::BeginPlay();
	StartLocation = GetActorLocation();
	const float Density = Field && Field->GaussianVolumeComponent
		? Field->GaussianVolumeComponent->SampleDensityAtWorldPosition(StartLocation) : 0.0f;
	PointLight->SetIntensity(MaxIntensity * FMath::Clamp(Density, 0.0f, 1.0f));
}

void AGaussianVolumeProbeActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
}
