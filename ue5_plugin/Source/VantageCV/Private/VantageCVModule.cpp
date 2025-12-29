/******************************************************************************
 * VantageCV - Plugin Module Implementation
 ******************************************************************************
 * File: VantageCVModule.cpp
 * Description: Implementation of VantageCV plugin module with Remote Control
 *              API endpoint registration for Python-UE5 communication
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#include "VantageCVModule.h"
#include "IRemoteControlModule.h"
#include "RemoteControlPreset.h"
#include "DataCapture.h"
#include "EngineUtils.h"
#include "Engine/World.h"

#define LOCTEXT_NAMESPACE "FVantageCVModule"

DEFINE_LOG_CATEGORY_STATIC(LogVantageCV, Log, All);

// Console command to trigger data capture
static FAutoConsoleCommand CaptureFrameCommand(
	TEXT("VantageCV.CaptureFrame"),
	TEXT("Capture a frame using the DataCapture actor in the current level"),
	FConsoleCommandDelegate::CreateStatic([]()
	{
		if (GEngine && GEngine->GetWorld())
		{
			UWorld* World = GEngine->GetWorld();
			for (TActorIterator<ADataCapture> It(World); It; ++It)
			{
				ADataCapture* DataCapture = *It;
				if (DataCapture)
				{
					UE_LOG(LogVantageCV, Log, TEXT("Executing CaptureFrame() on DataCapture actor"));
					FString OutputPath = FPaths::ProjectSavedDir() / TEXT("Screenshots/VantageCV");
					DataCapture->CaptureFrame(OutputPath, 1920, 1080);
					return;
				}
			}
			UE_LOG(LogVantageCV, Warning, TEXT("No DataCapture actor found in level"));
		}
	})
);

void FVantageCVModule::StartupModule()
{
	UE_LOG(LogVantageCV, Log, TEXT("VantageCV Module Starting..."));
	
	// Verify Remote Control module is available
	if (IRemoteControlModule* RemoteControlModule = FModuleManager::GetModulePtr<IRemoteControlModule>("RemoteControl"))
	{
		UE_LOG(LogVantageCV, Log, TEXT("Remote Control Module Found - Registering Endpoints"));
		RegisterRemoteControlEndpoints();
	}
	else
	{
		UE_LOG(LogVantageCV, Error, TEXT("Remote Control Module Not Found - Plugin functionality will be limited"));
	}
	
	UE_LOG(LogVantageCV, Log, TEXT("VantageCV Module Started Successfully"));
}

void FVantageCVModule::ShutdownModule()
{
	UE_LOG(LogVantageCV, Log, TEXT("VantageCV Module Shutting Down..."));
	UnregisterRemoteControlEndpoints();
	UE_LOG(LogVantageCV, Log, TEXT("VantageCV Module Shutdown Complete"));
}

void FVantageCVModule::RegisterRemoteControlEndpoints()
{
	// Remote Control endpoints are registered via the Remote Control Web API
	// The Python bridge communicates with UE5 via HTTP requests
	// Functions exposed via UFUNCTION(BlueprintCallable) are automatically available
	UE_LOG(LogVantageCV, Log, TEXT("Remote Control Endpoints Registered for SceneController and DataCapture actors"));
}

void FVantageCVModule::UnregisterRemoteControlEndpoints()
{
	// Cleanup Remote Control endpoints if needed
	UE_LOG(LogVantageCV, Log, TEXT("Remote Control Endpoints Unregistered"));
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FVantageCVModule, VantageCV)
