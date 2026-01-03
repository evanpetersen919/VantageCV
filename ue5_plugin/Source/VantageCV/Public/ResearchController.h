// Copyright VantageCV Research. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/SceneCapture2D.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "ResearchController.generated.h"

/**
 * Vehicle data for spawning
 */
USTRUCT(BlueprintType)
struct FResearchVehicleData
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString InstanceId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString VehicleClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString AssetPath;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Location;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FRotator Rotation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Scale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FLinearColor Color;
};

/**
 * Camera configuration for rendering
 */
USTRUCT(BlueprintType)
struct FResearchCameraConfig
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Location = FVector(0, 0, 150);  // 1.5m height in cm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FRotator Rotation = FRotator::ZeroRotator;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float FOV = 90.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Width = 1920;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Height = 1080;
};

/**
 * Frame capture result
 */
USTRUCT(BlueprintType)
struct FResearchFrameResult
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    bool bSuccess = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString ImagePath;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 FrameIndex = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float RenderTimeMs = 0.0f;
};

/**
 * Research Controller - Main actor for research-grade data generation
 * 
 * Responsibilities:
 * - Spawn vehicles from Python commands
 * - Control camera position/settings
 * - Capture frames to disk
 * - Provide 3D bounding box data for annotation
 * 
 * Logging: All operations logged to UE_LOG with structured format
 */
UCLASS()
class VANTAGECV_API AResearchController : public AActor
{
    GENERATED_BODY()

public:
    AResearchController();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:
    virtual void Tick(float DeltaTime) override;

    // ========================================
    // MODULE 1: Scene Control
    // ========================================

    /**
     * Initialize the research scene
     * @param SceneId Unique identifier for this scene
     * @param Seed Random seed for determinism
     * @return True if initialization successful
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Scene")
    bool InitializeScene(const FString& SceneId, int32 Seed);

    /**
     * Reset scene to initial state
     * @param NewSeed New random seed (uses increment if -1)
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Scene")
    void ResetScene(int32 NewSeed = -1);

    /**
     * Set time of day (lighting)
     * @param bIsDay True for daytime, false for night
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Scene")
    void SetTimeOfDay(bool bIsDay);

    // ========================================
    // MODULE 2: Vehicle Spawning
    // ========================================
    // NOTE: These methods spawn vehicles at arbitrary coordinates.
    // For anchor-driven spawning, use UAnchorSpawnSystem instead.

    /**
     * @deprecated Use UAnchorSpawnSystem::SpawnParkingVehicles() or SpawnLaneVehicles()
     *             for anchor-based spawning with deterministic randomization.
     * 
     * Spawn a vehicle in the scene at arbitrary coordinates.
     * @param VehicleData Vehicle configuration
     * @return Spawned actor or nullptr on failure
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Vehicles",
        meta=(DeprecatedFunction, DeprecationMessage="Use UAnchorSpawnSystem for anchor-based spawning"))
    AActor* SpawnVehicle(const FResearchVehicleData& VehicleData);

    /**
     * @deprecated Use UAnchorSpawnSystem for anchor-based batch spawning.
     * 
     * Spawn multiple vehicles at arbitrary coordinates.
     * @param Vehicles Array of vehicle data
     * @return Number of vehicles successfully spawned
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Vehicles",
        meta=(DeprecatedFunction, DeprecationMessage="Use UAnchorSpawnSystem for anchor-based spawning"))
    int32 SpawnVehicles(const TArray<FResearchVehicleData>& Vehicles);

    /**
     * Clear all spawned vehicles
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Vehicles")
    void ClearVehicles();

    /**
     * Get vehicle count
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Vehicles")
    int32 GetVehicleCount() const { return SpawnedVehicles.Num(); }

    // ========================================
    // MODULE 3: Camera Control
    // ========================================

    /**
     * Configure camera for capture
     * @param Config Camera configuration
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Camera")
    void ConfigureCamera(const FResearchCameraConfig& Config);

    /**
     * Get current camera configuration
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Camera")
    FResearchCameraConfig GetCameraConfig() const { return CameraConfig; }

    // ========================================
    // MODULE 4: Render & Capture
    // ========================================

    /**
     * Capture current frame to disk
     * @param FrameIndex Frame number
     * @param OutputPath Full path to save image
     * @return Frame result with success/failure info
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Capture")
    FResearchFrameResult CaptureFrame(int32 FrameIndex, const FString& OutputPath);

    /**
     * Set output directory for captures
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Capture")
    void SetOutputDirectory(const FString& Path);

    // ========================================
    // MODULE 5: Annotation Support
    // ========================================

    /**
     * Get 3D bounding box for a vehicle
     * @param VehicleActor The vehicle actor
     * @param OutCenter Output center point (world space)
     * @param OutExtent Output half-extents
     * @return True if bounds computed successfully
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Annotation")
    bool GetVehicleBounds(AActor* VehicleActor, FVector& OutCenter, FVector& OutExtent) const;

    /**
     * Get all vehicle bounding boxes
     * @return Array of (InstanceId, Center, Extent) tuples
     */
    UFUNCTION(BlueprintCallable, Category = "Research|Annotation")
    TArray<FString> GetAllVehicleBoundsJSON() const;

    // ========================================
    // Logging
    // ========================================

    /**
     * Log structured message
     */
    void LogInfo(const FString& Module, const FString& Message, const TMap<FString, FString>& Data = {});
    void LogError(const FString& Module, const FString& Message, const FString& Reason, const FString& SuggestedFix = TEXT(""));

protected:
    // Scene state
    UPROPERTY()
    FString CurrentSceneId;

    UPROPERTY()
    int32 CurrentSeed = 0;

    UPROPERTY()
    int32 FrameCounter = 0;

    UPROPERTY()
    bool bIsInitialized = false;

    // Spawned vehicles
    UPROPERTY()
    TArray<AActor*> SpawnedVehicles;

    UPROPERTY()
    TMap<FString, AActor*> VehicleInstanceMap;

    // Camera
    UPROPERTY()
    USceneCaptureComponent2D* CaptureComponent;

    UPROPERTY()
    UTextureRenderTarget2D* RenderTarget;

    UPROPERTY()
    FResearchCameraConfig CameraConfig;

    // Output
    UPROPERTY()
    FString OutputDirectory;

    // Time of day
    UPROPERTY()
    bool bIsDaytime = true;

private:
    void SetupCaptureComponent();
    void UpdateRenderTarget(int32 Width, int32 Height);
    bool SaveRenderTargetToDisk(const FString& FilePath);
};
