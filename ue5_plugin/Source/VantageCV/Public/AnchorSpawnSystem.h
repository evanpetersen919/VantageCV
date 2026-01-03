// Copyright VantageCV Research. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AnchorSpawnSystem.generated.h"

/**
 * Anchor type enumeration
 */
UENUM(BlueprintType)
enum class EAnchorType : uint8
{
    Parking,
    RoadLaneStart,
    RoadLaneEnd,
    SidewalkBound,
    Exclusion,
    Background
};

/**
 * Parking spawn mode
 */
UENUM(BlueprintType)
enum class EParkingMode : uint8
{
    PullIn,         // Vehicle faces forward (same as anchor)
    ReverseIn       // Vehicle faces backward (180° from anchor)
};

/**
 * Single anchor definition - references an existing actor in the level
 */
USTRUCT(BlueprintType)
struct FAnchorDefinition
{
    GENERATED_BODY()

    /** Name of the actor in the level (e.g., "StaticMeshActor_15") */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString ActorName;

    /** Type of anchor */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EAnchorType Type = EAnchorType::Parking;

    /** Optional group ID (e.g., lane number) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString GroupId;

    /** Cached world transform (populated at runtime) */
    FTransform CachedTransform;

    /** Whether this anchor was successfully resolved */
    bool bIsValid = false;
};

/**
 * Lane definition - a directed segment between two anchors
 */
USTRUCT(BlueprintType)
struct FLaneDefinition
{
    GENERATED_BODY()

    /** Lane identifier */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString LaneId;

    /** Start anchor actor name */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString StartAnchorName;

    /** End anchor actor name */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString EndAnchorName;

    /** Lane width for lateral offset */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float LaneWidth = 350.0f;

    /** Cached transforms */
    FTransform StartTransform;
    FTransform EndTransform;
    FVector Direction;
    float Length = 0.0f;
    bool bIsValid = false;
};

/**
 * Sidewalk bounds definition
 */
USTRUCT(BlueprintType)
struct FSidewalkBounds
{
    GENERATED_BODY()

    /** First corner anchor name */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Anchor1Name;

    /** Second corner anchor name */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Anchor2Name;

    /** Computed axis-aligned bounds */
    FBox Bounds;
    bool bIsValid = false;
};

/**
 * Vehicle spawn result
 */
USTRUCT(BlueprintType)
struct FSpawnResult
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly)
    bool bSuccess = false;

    UPROPERTY(BlueprintReadOnly)
    FString InstanceId;

    UPROPERTY(BlueprintReadOnly)
    AActor* SpawnedActor = nullptr;

    UPROPERTY(BlueprintReadOnly)
    FString AnchorName;

    UPROPERTY(BlueprintReadOnly)
    FTransform FinalTransform;

    UPROPERTY(BlueprintReadOnly)
    FString FailureReason;
};

/**
 * Spawn configuration for a single vehicle
 */
USTRUCT(BlueprintType)
struct FVehicleSpawnConfig
{
    GENERATED_BODY()

    /** Asset path to vehicle mesh or blueprint */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString AssetPath;

    /** Vehicle class identifier (for logging) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString VehicleClass;

    /** Scale multiplier */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Scale = 1.0f;
};

/**
 * Configuration for anchor-based spawning
 */
USTRUCT(BlueprintType)
struct FAnchorSpawnConfig
{
    GENERATED_BODY()

    // ========== Parking Configuration ==========

    /** Parking slot anchor names */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FString> ParkingAnchors;

    /** Maximum random XY jitter for parking (in cm) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float ParkingPositionJitter = 10.0f;

    /** Maximum random yaw offset after forward/reverse selection (degrees) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float ParkingYawJitter = 5.0f;

    /** Probability of reverse parking (0.0 to 1.0) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float ReverseParkingProbability = 0.3f;

    // ========== Lane Configuration ==========

    /** Lane definitions */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FLaneDefinition> Lanes;

    /** Maximum lateral offset from lane center (in cm) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float LaneLateralJitter = 30.0f;

    /** Maximum yaw offset for lane vehicles (degrees) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float LaneYawJitter = 2.0f;

    // ========== Sidewalk Configuration ==========

    /** Sidewalk bounds definition */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FSidewalkBounds SidewalkBounds;

    // ========== Locked Actors ==========

    /** Background/environment actors that must never be modified */
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FString> LockedActors;
};

/**
 * Deterministic random stream wrapper with logging
 */
class FDeterministicRandom
{
public:
    void Initialize(int32 Seed);
    
    /** Get random float in range [0, 1) */
    float FRand();
    
    /** Get random float in range [Min, Max] */
    float FRandRange(float Min, float Max);
    
    /** Get random int in range [Min, Max] */
    int32 RandRange(int32 Min, int32 Max);
    
    /** Get random bool with given probability of true */
    bool RandBool(float TrueProbability = 0.5f);
    
    int32 GetSeed() const { return CurrentSeed; }
    int32 GetCallCount() const { return CallCount; }

private:
    FRandomStream Stream;
    int32 CurrentSeed = 0;
    int32 CallCount = 0;
};

/**
 * Anchor-based Spawn System
 * 
 * Provides deterministic, data-driven spawning using existing anchor actors.
 * No hardcoded coordinates - all positions derived from level anchors.
 */
UCLASS()
class VANTAGECV_API UAnchorSpawnSystem : public UObject
{
    GENERATED_BODY()

public:
    UAnchorSpawnSystem();

    // ========================================
    // Initialization
    // ========================================

    /**
     * Initialize the spawn system with a world reference and config
     * @param InWorld The world to spawn in
     * @param Config Spawn configuration
     * @param Seed Random seed for determinism
     * @return True if initialization successful
     */
    bool Initialize(UWorld* InWorld, const FAnchorSpawnConfig& Config, int32 Seed);

    /**
     * Re-initialize with a new seed (keeps same config)
     */
    void ReinitializeWithSeed(int32 NewSeed);

    // ========================================
    // Anchor Resolution
    // ========================================

    /**
     * Find and cache all anchor transforms from the level
     * @return Number of successfully resolved anchors
     */
    int32 ResolveAnchors();

    /**
     * Get actor by name from the level
     * @param ActorName Name of the actor (label in Outliner)
     * @return Actor pointer or nullptr
     */
    AActor* FindActorByName(const FString& ActorName) const;

    // ========================================
    // Parking Spawning
    // ========================================

    /**
     * Spawn vehicles in parking slots
     * @param VehicleConfigs Vehicle configurations (one per slot, or cycles)
     * @param MaxVehicles Maximum vehicles to spawn (-1 = fill all slots)
     * @return Array of spawn results
     */
    TArray<FSpawnResult> SpawnParkingVehicles(
        const TArray<FVehicleSpawnConfig>& VehicleConfigs,
        int32 MaxVehicles = -1
    );

    /**
     * Spawn a single vehicle at a specific parking anchor
     */
    FSpawnResult SpawnAtParkingSlot(
        const FString& AnchorName,
        const FVehicleSpawnConfig& Config,
        EParkingMode Mode = EParkingMode::PullIn
    );

    // ========================================
    // Lane Spawning
    // ========================================

    /**
     * Spawn vehicles along lanes
     * @param VehicleConfigs Vehicle configurations
     * @param VehiclesPerLane Number of vehicles per lane
     * @return Array of spawn results
     */
    TArray<FSpawnResult> SpawnLaneVehicles(
        const TArray<FVehicleSpawnConfig>& VehicleConfigs,
        int32 VehiclesPerLane = 2
    );

    /**
     * Spawn a single vehicle at a position along a lane
     * @param LaneId Lane identifier
     * @param T Interpolation parameter [0, 1] along lane
     */
    FSpawnResult SpawnAlongLane(
        const FString& LaneId,
        float T,
        const FVehicleSpawnConfig& Config
    );

    // ========================================
    // Sidewalk Props
    // ========================================

    /**
     * Spawn props within sidewalk bounds
     * @param PropAssetPaths Asset paths for props
     * @param Count Number of props to spawn
     * @return Array of spawn results
     */
    TArray<FSpawnResult> SpawnSidewalkProps(
        const TArray<FString>& PropAssetPaths,
        int32 Count
    );

    // ========================================
    // Cleanup
    // ========================================

    /**
     * Clear all spawned actors
     */
    void ClearAllSpawned();

    /**
     * Get all spawned actors
     */
    TArray<AActor*> GetSpawnedActors() const { return SpawnedActors; }

    /**
     * Get spawn count
     */
    int32 GetSpawnCount() const { return SpawnedActors.Num(); }

    // ========================================
    // Collision Detection
    // ========================================

    /**
     * Check if a spawn transform would overlap with existing vehicles
     * @param Transform Proposed spawn transform
     * @param VehicleExtent Half-extent of vehicle bounds
     * @return True if overlap detected
     */
    bool CheckOverlap(const FTransform& Transform, const FVector& VehicleExtent) const;

    // ========================================
    // Logging
    // ========================================

    void LogInfo(const FString& Module, const FString& Message, const TMap<FString, FString>& Data = {});
    void LogError(const FString& Module, const FString& Message, const FString& Reason, const FString& SuggestedFix = TEXT(""));
    void LogSpawnResult(const FSpawnResult& Result);

protected:
    // World reference
    UPROPERTY()
    UWorld* World = nullptr;

    // Configuration
    FAnchorSpawnConfig Config;

    // Random stream
    FDeterministicRandom Random;

    // Resolved anchors
    TMap<FString, FAnchorDefinition> ResolvedAnchors;

    // Spawned actors
    UPROPERTY()
    TArray<AActor*> SpawnedActors;

    // Instance counter for unique IDs
    int32 InstanceCounter = 0;

    // ========================================
    // Internal Helpers
    // ========================================

    /** Compute spawn transform for parking slot */
    FTransform ComputeParkingTransform(const FAnchorDefinition& Anchor, EParkingMode Mode);

    /** Compute spawn transform along lane */
    FTransform ComputeLaneTransform(const FLaneDefinition& Lane, float T);

    /** Compute random position within sidewalk bounds */
    FVector ComputeSidewalkPosition();

    /** Apply ground alignment via raycast */
    float GetGroundZ(const FVector& Location) const;

    /** Spawn actor from asset path */
    AActor* SpawnActorFromAsset(const FString& AssetPath, const FTransform& Transform, const FString& InstanceId);

    /** Generate unique instance ID */
    FString GenerateInstanceId(const FString& Prefix);
};
