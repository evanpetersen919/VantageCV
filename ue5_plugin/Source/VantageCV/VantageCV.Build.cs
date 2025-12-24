/******************************************************************************
 * VantageCV - Unreal Engine 5 Plugin Build Configuration
 ******************************************************************************
 * File: VantageCV.Build.cs
 * Description: Build configuration for VantageCV UE5 plugin, specifying
 *              module dependencies and compilation settings
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

using UnrealBuildTool;

public class VantageCV : ModuleRules
{
	public VantageCV(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;
		
		PublicIncludePaths.AddRange(
			new string[] {
				// ... add public include paths required here ...
			}
			);
				
		
		PrivateIncludePaths.AddRange(
			new string[] {
				// ... add other private include paths required here ...
			}
			);
			
		
		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				"CoreUObject",
				"Engine",
				"InputCore",
				"RenderCore",
				"RHI",
				"ImageWrapper",
				"RemoteControl",
				"RemoteControlProtocol",
				"ImageWriteQueue",
				"JsonUtilities",
				"Json"
			}
			);
			
		
		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"CoreUObject",
				"Engine",
				"Slate",
				"SlateCore"
			}
			);
		
		
		DynamicallyLoadedModuleNames.AddRange(
			new string[]
			{
				// ... add any modules that your module loads dynamically here ...
			}
			);
	}
}
