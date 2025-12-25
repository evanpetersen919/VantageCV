/******************************************************************************
 * VantageCV - Engine Subsystem for Remote Control Access
 ******************************************************************************
 * File: VantageCVSubsystem.h
 * Description: Engine subsystem that provides globally accessible functions
 *              for Python/Remote Control API to trigger data capture
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/EngineSubsystem.h"
#include "VantageCVSubsystem.generated.h"

/**
 * VantageCV Engine Subsystem
 * Provides globally accessible functions that can be called via Remote Control API
 * This is the research-grade approach for Python-UE5 communication
 */
UCLASS()
class VANTAGECV_API UVantageCVSubsystem : public UEngineSubsystem
{
	GENERATED_BODY()

public:
	// Subsystem lifecycle
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/**
	 * Capture a frame from the first DataCapture actor found in the current level
	 * Can be called via Remote Control API from Python
	 * @return True if capture was successful, false otherwise
	 */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	bool CaptureFrame();

	/**
	 * Randomize scene lighting using the first SceneController actor
	 * @return True if randomization was successful
	 */
	UFUNCTION(BlueprintCallable, Category = "VantageCV")
	bool RandomizeScene();
};
