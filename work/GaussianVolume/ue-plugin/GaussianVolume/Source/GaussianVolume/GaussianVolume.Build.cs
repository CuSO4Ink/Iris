using UnrealBuildTool;
using System.IO;

public class GaussianVolume : ModuleRules
{
	public GaussianVolume(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				"CoreUObject",
				"Engine",
				"Json",
			}
		);

		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"RenderCore",
				"RHI",
				"Renderer",
				"Projects",
			}
		);

		// Access to FPostProcessingInputs (Internal/PostProcess/PostProcessInputs.h)
		// and other Renderer Internal/Private headers not in the public include path.
		string RendererModuleDir = GetModuleDirectory("Renderer");
		PrivateIncludePaths.Add(Path.Combine(RendererModuleDir, "Internal"));
		PrivateIncludePaths.Add(Path.Combine(RendererModuleDir, "Internal/PostProcess"));
		PrivateIncludePaths.Add(Path.Combine(RendererModuleDir, "Private"));
		PrivateIncludePaths.Add(Path.Combine(
			EngineDirectory,
			"Source",
			"ThirdParty",
			"OpenVDB",
			"openvdb-13.0.0",
			"nanovdb"));
		PublicDefinitions.Add("GAUSSIANVOLUME_WITH_NANOVDB=1");

		// Map "/GaussianVolume" virtual shader directory to our Shaders folder
		if (Target.Type == TargetType.Editor)
		{
			PrivateIncludePaths.Add("GaussianVolume/Private");
			bUseRTTI = true;
			bEnableExceptions = true;
			PublicDefinitions.Add("GAUSSIANVOLUME_WITH_OPENVDB=1");
			AddEngineThirdPartyPrivateStaticDependencies(Target,
				"IntelTBB",
				"Blosc",
				"zlib",
				"Boost",
				"OpenVDB"
			);
		}
		else
		{
			PublicDefinitions.Add("GAUSSIANVOLUME_WITH_OPENVDB=0");
		}
	}
}
