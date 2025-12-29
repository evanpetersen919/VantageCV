/******************************************************************************
 * VantageCV - Engine Subsystem Implementation
 ******************************************************************************
 * File: VantageCVSubsystem.cpp
 * Description: Implementation of globally accessible VantageCV functions
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#include "VantageCVSubsystem.h"
#include "DataCapture.h"
#include "SceneController.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Engine/Engine.h"

DEFINE_LOG_CATEGORY_STATIC(LogVantageCVSubsystem, Log, All);

void UVantageCVSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	UE_LOG(LogVantageCVSubsystem, Log, TEXT("VantageCV Subsystem Initialized - Remote Control functions available"));
}

void UVantageCVSubsystem::Deinitialize()
{
	UE_LOG(LogVantageCVSubsystem, Log, TEXT("VantageCV Subsystem Deinitialized"));
	Super::Deinitialize();
}

bool UVantageCVSubsystem::CaptureFrame()
{
	UE_LOG(LogVantageCVSubsystem, Log, TEXT("CaptureFrame() called via Remote Control API"));
	
	// Get the current world
	if (!GEngine)
	{
		UE_LOG(LogVantageCVSubsystem, Error, TEXT("GEngine is null"));
		return false;
	}

	UWorld* World = GEngine->GetCurrentPlayWorld();
	if (!World)
	{
		// If not in play mode, try to get editor world
		World = GEngine->GetWorld();
	}

	if (!World)
	{
		UE_LOG(LogVantageCVSubsystem, Error, TEXT("No valid world found"));
		return false;
	}

	// Find the first DataCapture actor in the level
	for (TActorIterator<ADataCapture> It(World); It; ++It)
	{
		ADataCapture* DataCapture = *It;
		if (DataCapture && IsValid(DataCapture))
		{
			UE_LOG(LogVantageCVSubsystem, Log, TEXT("Found DataCapture actor: %s"), *DataCapture->GetName());
			FString OutputPath = FPaths::ProjectSavedDir() / TEXT("Screenshots/VantageCV");
			DataCapture->CaptureFrame(OutputPath, 1920, 1080);
			UE_LOG(LogVantageCVSubsystem, Log, TEXT("CaptureFrame() executed successfully"));
			return true;
		}
	}

	UE_LOG(LogVantageCVSubsystem, Warning, TEXT("No DataCapture actor found in level"));
	return false;
}

bool UVantageCVSubsystem::RandomizeScene()
{
	UE_LOG(LogVantageCVSubsystem, Log, TEXT("RandomizeScene() called via Remote Control API"));
	
	if (!GEngine)
	{
		UE_LOG(LogVantageCVSubsystem, Error, TEXT("GEngine is null"));
		return false;
	}

	UWorld* World = GEngine->GetCurrentPlayWorld();
	if (!World)
	{
		World = GEngine->GetWorld();
	}

	if (!World)
	{
		UE_LOG(LogVantageCVSubsystem, Error, TEXT("No valid world found"));
		return false;
	}

	// Find the first SceneController actor
	for (TActorIterator<ASceneController> It(World); It; ++It)
	{
		ASceneController* SceneController = *It;
		if (SceneController && IsValid(SceneController))
		{
			UE_LOG(LogVantageCVSubsystem, Log, TEXT("Found SceneController actor: %s"), *SceneController->GetName());
			SceneController->RandomizeLighting(100.0f, 1000.0f, 4000.0f, 7000.0f);
			TArray<FString> TargetTags = {TEXT("Ground")};
			SceneController->RandomizeMaterials(TargetTags);
			UE_LOG(LogVantageCVSubsystem, Log, TEXT("Scene randomization complete"));
			return true;
		}
	}

	UE_LOG(LogVantageCVSubsystem, Warning, TEXT("No SceneController actor found in level"));
	return false;
}
