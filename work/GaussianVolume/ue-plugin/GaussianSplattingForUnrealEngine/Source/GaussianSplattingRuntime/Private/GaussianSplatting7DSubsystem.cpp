#include "GaussianSplatting7DSubsystem.h"

#include "GaussianSplatting7DComponent.h"
#include "GaussianSplattingSceneViewExtension.h"
#include "RenderingThread.h"
#include "SceneViewExtension.h"

void UGaussianSplatting7DWorldSubsystem::Deinitialize()
{
	FlushRenderingCommands();
	Renderer.Reset();
	ActiveComponent.Reset();
	Super::Deinitialize();
}

void UGaussianSplatting7DWorldSubsystem::EnsureRenderer()
{
	if (!Renderer.IsValid() && GetWorld())
	{
		Renderer =
			FSceneViewExtensions::NewExtension<FGaussianSplattingSceneViewExtension>(
				GetWorld());
	}
}

void UGaussianSplatting7DWorldSubsystem::RegisterComponent(
	UGaussianSplatting7DComponent* Component)
{
	if (!Component)
	{
		return;
	}
	EnsureRenderer();
	// ponytail: one active cloud is enough for the first VDB A/B; merge sources
	// only after a production scene proves multi-cloud support is needed.
	ActiveComponent = Component;
}

void UGaussianSplatting7DWorldSubsystem::UnregisterComponent(
	UGaussianSplatting7DComponent* Component)
{
	if (ActiveComponent.Get() != Component)
	{
		return;
	}
	ActiveComponent.Reset();
	if (Renderer.IsValid())
	{
		Renderer->UpdateData_GameThread(TArray<FVector4f>());
	}
}

void UGaussianSplatting7DWorldSubsystem::UpdateData(
	UGaussianSplatting7DComponent* Component,
	TArray<FVector4f>&& RawData)
{
	if (!Component)
	{
		return;
	}
	RegisterComponent(Component);
	Renderer->UpdateData_GameThread(MoveTemp(RawData));
}

void UGaussianSplatting7DWorldSubsystem::UpdateParameters(
	UGaussianSplatting7DComponent* Component,
	const GaussianSplatting7DRGS::FSourceParameters& Parameters)
{
	if (!Component || ActiveComponent.Get() != Component)
	{
		return;
	}
	EnsureRenderer();
	Renderer->UpdateParameters_GameThread(Parameters);
}
