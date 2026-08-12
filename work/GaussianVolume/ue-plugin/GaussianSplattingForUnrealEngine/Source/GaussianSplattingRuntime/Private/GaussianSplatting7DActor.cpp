#include "GaussianSplatting7DActor.h"

#include "GaussianSplatting7DComponent.h"

AGaussianSplatting7DActor::AGaussianSplatting7DActor()
{
	GS7DComponent = CreateDefaultSubobject<UGaussianSplatting7DComponent>(TEXT("GS7DComponent"));
	SetRootComponent(GS7DComponent);
}
