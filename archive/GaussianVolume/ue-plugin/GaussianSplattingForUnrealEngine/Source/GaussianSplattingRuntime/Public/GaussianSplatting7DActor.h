#pragma once

#include "GameFramework/Actor.h"
#include "GaussianSplatting7DActor.generated.h"

class UGaussianSplatting7DComponent;

UCLASS()
class GAUSSIANSPLATTINGRUNTIME_API AGaussianSplatting7DActor final : public AActor
{
	GENERATED_BODY()

public:
	AGaussianSplatting7DActor();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="7DRGS")
	TObjectPtr<UGaussianSplatting7DComponent> GS7DComponent;
};
