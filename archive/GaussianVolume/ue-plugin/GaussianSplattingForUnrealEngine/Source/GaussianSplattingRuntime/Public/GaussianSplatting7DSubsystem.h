#pragma once

#include "GaussianSplatting7DTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "GaussianSplatting7DSubsystem.generated.h"

class FGaussianSplattingSceneViewExtension;
class UGaussianSplatting7DComponent;

UCLASS()
class GAUSSIANSPLATTINGRUNTIME_API UGaussianSplatting7DWorldSubsystem final : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Deinitialize() override;

	void RegisterComponent(UGaussianSplatting7DComponent* Component);
	void UnregisterComponent(UGaussianSplatting7DComponent* Component);
	void UpdateData(UGaussianSplatting7DComponent* Component, TArray<FVector4f>&& RawData);
	void UpdateParameters(
		UGaussianSplatting7DComponent* Component,
		const GaussianSplatting7DRGS::FSourceParameters& Parameters);

private:
	void EnsureRenderer();

	TWeakObjectPtr<UGaussianSplatting7DComponent> ActiveComponent;
	TSharedPtr<FGaussianSplattingSceneViewExtension, ESPMode::ThreadSafe> Renderer;
};
