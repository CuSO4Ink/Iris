// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GaussianVolumeProbeActor.generated.h"

class AGaussianVolumeActor;
class UPointLightComponent;

/** Minimal second consumer proving the rendered Gaussian field is queryable. */
UCLASS(ClassGroup=(Rendering), meta=(DisplayName="Gaussian Volume Probe"))
class GAUSSIANVOLUME_API AGaussianVolumeProbeActor : public AActor
{
	GENERATED_BODY()

public:
	AGaussianVolumeProbeActor();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="GaussianVolume")
	TObjectPtr<AGaussianVolumeActor> Field;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="GaussianVolume")
	TObjectPtr<UPointLightComponent> PointLight;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="GaussianVolume", meta=(ClampMin="0.0"))
	float MaxIntensity = 5000.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="GaussianVolume")
	FVector Travel = FVector(0.0, 500.0, 0.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="GaussianVolume", meta=(ClampMin="0.0"))
	float Speed = 0.5f;

private:
	FVector StartLocation;
};
