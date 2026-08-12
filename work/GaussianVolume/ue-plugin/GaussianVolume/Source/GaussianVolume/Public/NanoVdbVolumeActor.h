// Copyright 2026 Violina. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NanoVdbVolumeActor.generated.h"

class UNanoVdbVolumeComponent;
class USceneComponent;

UCLASS(ClassGroup=(Rendering), meta=(DisplayName="NanoVDB Volume Baseline"))
class GAUSSIANVOLUME_API ANanoVdbVolumeActor : public AActor
{
	GENERATED_BODY()

public:
	ANanoVdbVolumeActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "NanoVDB")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "NanoVDB")
	TObjectPtr<UNanoVdbVolumeComponent> NanoVdbVolumeComponent;
};
