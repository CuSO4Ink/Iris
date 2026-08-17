// Copyright 2026 Violina. All Rights Reserved.

#include "NanoVdbVolumeActor.h"
#include "NanoVdbVolumeComponent.h"
#include "Components/SceneComponent.h"

ANanoVdbVolumeActor::ANanoVdbVolumeActor()
{
	PrimaryActorTick.bCanEverTick = false;
	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	RootComponent = SceneRoot;
	NanoVdbVolumeComponent = CreateDefaultSubobject<UNanoVdbVolumeComponent>(
		TEXT("NanoVdbVolumeComponent"));
}
