using UnrealBuildTool;
using System.IO;

public class GaussianSplattingRuntime : ModuleRules
{
	public GaussianSplattingRuntime(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new[]
		{
			"Core",
			"CoreUObject",
			"Engine"
		});

		PrivateDependencyModuleNames.AddRange(new[]
		{
			"Projects",
			"RenderCore",
			"Renderer",
			"RHI"
		});

		string RendererModuleDir = GetModuleDirectory("Renderer");
		PrivateIncludePaths.Add(Path.Combine(RendererModuleDir, "Internal"));
		PrivateIncludePaths.Add(Path.Combine(RendererModuleDir, "Internal/PostProcess"));
		PrivateIncludePaths.Add(Path.Combine(RendererModuleDir, "Private"));
	}
}
