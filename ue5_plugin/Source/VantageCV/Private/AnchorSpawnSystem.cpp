// Copyright VantageCV Research. All Rights Reserved.

#include "AnchorSpawnSystem.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Kismet/GameplayStatics.h"
#include "EngineUtils.h"  // For TActorIterator
#include "DrawDebugHelpers.h"

DEFINE_LOG_CATEGORY_STATIC(LogAnchorSpawn, Log, All);

// ============================================================================
// FDeterministicRandom Implementation
// ============================================================================

void FDeterministicRandom::Initialize(int32 Seed)
{
    CurrentSeed = Seed;
    Stream.Initialize(Seed);
    CallCount = 0;
}

float FDeterministicRandom::FRand()
{
    CallCount++;
    return Stream.FRand();
}

float FDeterministicRandom::FRandRange(float Min, float Max)
{
    CallCount++;
    return Stream.FRandRange(Min, Max);
}

int32 FDeterministicRandom::RandRange(int32 Min, int32 Max)
{
    CallCount++;
    return Stream.RandRange(Min, Max);
}

bool FDeterministicRandom::RandBool(float TrueProbability)
{
    return FRand() < TrueProbability;
}

// ============================================================================
// UAnchorSpawnSystem Implementation
// ============================================================================

UAnchorSpawnSystem::UAnchorSpawnSystem()
{
}

bool UAnchorSpawnSystem::Initialize(UWorld* InWorld, const FAnchorSpawnConfig& InConfig, int32 Seed)
{
    if (!InWorld)
    {
        LogError(TEXT("AnchorSpawnSystem"), TEXT("Initialization failed"), TEXT("World is null"));
        return false;
    }

    World = InWorld;
    Config = InConfig;
    Random.Initialize(Seed);
    InstanceCounter = 0;

    LogInfo(TEXT("AnchorSpawnSystem"), TEXT("Initializing"),
        {
            {TEXT("seed"), FString::FromInt(Seed)},
            {TEXT("parking_anchors"), FString::FromInt(Config.ParkingAnchors.Num())},
            {TEXT("lanes"), FString::FromInt(Config.Lanes.Num())},
            {TEXT("locked_actors"), FString::FromInt(Config.LockedActors.Num())}
        });

    // Resolve all anchors
    int32 ResolvedCount = ResolveAnchors();

    LogInfo(TEXT("AnchorSpawnSystem"), TEXT("Initialization complete"),
        {
            {TEXT("resolved_anchors"), FString::FromInt(ResolvedCount)},
            {TEXT("seed"), FString::FromInt(Seed)}
        });

    return ResolvedCount > 0;
}

void UAnchorSpawnSystem::ReinitializeWithSeed(int32 NewSeed)
{
    Random.Initialize(NewSeed);
    InstanceCounter = 0;
    ClearAllSpawned();

    LogInfo(TEXT("AnchorSpawnSystem"), TEXT("Reinitialized with new seed"),
        {
            {TEXT("new_seed"), FString::FromInt(NewSeed)}
        });
}

// ============================================================================
// Anchor Resolution
// ============================================================================

int32 UAnchorSpawnSystem::ResolveAnchors()
{
    ResolvedAnchors.Empty();
    int32 ResolvedCount = 0;

    // Resolve parking anchors
    for (const FString& AnchorName : Config.ParkingAnchors)
    {
        AActor* Actor = FindActorByName(AnchorName);
        if (Actor)
        {
            FAnchorDefinition Anchor;
            Anchor.ActorName = AnchorName;
            Anchor.Type = EAnchorType::Parking;
            Anchor.CachedTransform = Actor->GetActorTransform();
            Anchor.bIsValid = true;
            ResolvedAnchors.Add(AnchorName, Anchor);
            ResolvedCount++;

            LogInfo(TEXT("AnchorResolver"), TEXT("Parking anchor resolved"),
                {
                    {TEXT("name"), AnchorName},
                    {TEXT("location"), FString::Printf(TEXT("(%.1f, %.1f, %.1f)"),
                        Anchor.CachedTransform.GetLocation().X,
                        Anchor.CachedTransform.GetLocation().Y,
                        Anchor.CachedTransform.GetLocation().Z)},
                    {TEXT("yaw"), FString::Printf(TEXT("%.1f"), Anchor.CachedTransform.Rotator().Yaw)}
                });
        }
        else
        {
            LogError(TEXT("AnchorResolver"), TEXT("Parking anchor not found"),
                AnchorName,
                TEXT("Check actor name in Outliner matches exactly"));
        }
    }

    // Resolve lane anchors
    for (FLaneDefinition& Lane : Config.Lanes)
    {
        AActor* StartActor = FindActorByName(Lane.StartAnchorName);
        AActor* EndActor = FindActorByName(Lane.EndAnchorName);

        if (StartActor && EndActor)
        {
            Lane.StartTransform = StartActor->GetActorTransform();
            Lane.EndTransform = EndActor->GetActorTransform();

            FVector StartLoc = Lane.StartTransform.GetLocation();
            FVector EndLoc = Lane.EndTransform.GetLocation();
            Lane.Direction = (EndLoc - StartLoc).GetSafeNormal();
            Lane.Length = FVector::Dist(StartLoc, EndLoc);
            Lane.bIsValid = true;
            ResolvedCount += 2;

            // Cache start/end as anchors
            FAnchorDefinition StartAnchor;
            StartAnchor.ActorName = Lane.StartAnchorName;
            StartAnchor.Type = EAnchorType::RoadLaneStart;
            StartAnchor.GroupId = Lane.LaneId;
            StartAnchor.CachedTransform = Lane.StartTransform;
            StartAnchor.bIsValid = true;
            ResolvedAnchors.Add(Lane.StartAnchorName, StartAnchor);

            FAnchorDefinition EndAnchor;
            EndAnchor.ActorName = Lane.EndAnchorName;
            EndAnchor.Type = EAnchorType::RoadLaneEnd;
            EndAnchor.GroupId = Lane.LaneId;
            EndAnchor.CachedTransform = Lane.EndTransform;
            EndAnchor.bIsValid = true;
            ResolvedAnchors.Add(Lane.EndAnchorName, EndAnchor);

            LogInfo(TEXT("AnchorResolver"), TEXT("Lane resolved"),
                {
                    {TEXT("lane_id"), Lane.LaneId},
                    {TEXT("start"), Lane.StartAnchorName},
                    {TEXT("end"), Lane.EndAnchorName},
                    {TEXT("length"), FString::Printf(TEXT("%.1f"), Lane.Length)},
                    {TEXT("direction"), FString::Printf(TEXT("(%.2f, %.2f, %.2f)"),
                        Lane.Direction.X, Lane.Direction.Y, Lane.Direction.Z)}
                });
        }
        else
        {
            Lane.bIsValid = false;
            LogError(TEXT("AnchorResolver"), TEXT("Lane anchor(s) not found"),
                FString::Printf(TEXT("Lane %s: Start=%s End=%s"),
                    *Lane.LaneId,
                    StartActor ? TEXT("OK") : *Lane.StartAnchorName,
                    EndActor ? TEXT("OK") : *Lane.EndAnchorName),
                TEXT("Ensure both anchor actors exist in level"));
        }
    }

    // Resolve sidewalk bounds
    AActor* SW1 = FindActorByName(Config.SidewalkBounds.Anchor1Name);
    AActor* SW2 = FindActorByName(Config.SidewalkBounds.Anchor2Name);

    if (SW1 && SW2)
    {
        FVector P1 = SW1->GetActorLocation();
        FVector P2 = SW2->GetActorLocation();

        // Create axis-aligned bounding box
        FVector Min(FMath::Min(P1.X, P2.X), FMath::Min(P1.Y, P2.Y), FMath::Min(P1.Z, P2.Z));
        FVector Max(FMath::Max(P1.X, P2.X), FMath::Max(P1.Y, P2.Y), FMath::Max(P1.Z, P2.Z));

        Config.SidewalkBounds.Bounds = FBox(Min, Max);
        Config.SidewalkBounds.bIsValid = true;
        ResolvedCount += 2;

        LogInfo(TEXT("AnchorResolver"), TEXT("Sidewalk bounds resolved"),
            {
                {TEXT("min"), FString::Printf(TEXT("(%.1f, %.1f, %.1f)"), Min.X, Min.Y, Min.Z)},
                {TEXT("max"), FString::Printf(TEXT("(%.1f, %.1f, %.1f)"), Max.X, Max.Y, Max.Z)}
            });
    }
    else if (!Config.SidewalkBounds.Anchor1Name.IsEmpty() || !Config.SidewalkBounds.Anchor2Name.IsEmpty())
    {
        LogError(TEXT("AnchorResolver"), TEXT("Sidewalk anchor(s) not found"),
            FString::Printf(TEXT("Anchor1=%s Anchor2=%s"),
                SW1 ? TEXT("OK") : *Config.SidewalkBounds.Anchor1Name,
                SW2 ? TEXT("OK") : *Config.SidewalkBounds.Anchor2Name),
            TEXT("Ensure both sidewalk bound actors exist"));
    }

    return ResolvedCount;
}

AActor* UAnchorSpawnSystem::FindActorByName(const FString& ActorName) const
{
    if (!World || ActorName.IsEmpty())
    {
        return nullptr;
    }

    // Iterate through all actors and find by name
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (Actor && Actor->GetName() == ActorName)
        {
            return Actor;
        }
    }

    // Also try GetFName comparison
    FName TargetName(*ActorName);
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (Actor && Actor->GetFName() == TargetName)
        {
            return Actor;
        }
    }

    return nullptr;
}

// ============================================================================
// Parking Spawning
// ============================================================================

TArray<FSpawnResult> UAnchorSpawnSystem::SpawnParkingVehicles(
    const TArray<FVehicleSpawnConfig>& VehicleConfigs,
    int32 MaxVehicles)
{
    TArray<FSpawnResult> Results;

    if (VehicleConfigs.Num() == 0)
    {
        LogError(TEXT("ParkingSpawner"), TEXT("No vehicle configs provided"), TEXT("VehicleConfigs array is empty"));
        return Results;
    }

    int32 SlotCount = Config.ParkingAnchors.Num();
    int32 VehiclesToSpawn = (MaxVehicles < 0) ? SlotCount : FMath::Min(MaxVehicles, SlotCount);

    LogInfo(TEXT("ParkingSpawner"), TEXT("Spawning parking vehicles"),
        {
            {TEXT("slots_available"), FString::FromInt(SlotCount)},
            {TEXT("vehicles_to_spawn"), FString::FromInt(VehiclesToSpawn)},
            {TEXT("seed"), FString::FromInt(Random.GetSeed())}
        });

    // Shuffle slot order for variety
    TArray<int32> SlotIndices;
    for (int32 i = 0; i < SlotCount; i++)
    {
        SlotIndices.Add(i);
    }

    // Fisher-Yates shuffle
    for (int32 i = SlotCount - 1; i > 0; i--)
    {
        int32 j = Random.RandRange(0, i);
        SlotIndices.Swap(i, j);
    }

    // Spawn vehicles
    int32 SpawnedCount = 0;
    for (int32 i = 0; i < VehiclesToSpawn && i < SlotIndices.Num(); i++)
    {
        int32 SlotIndex = SlotIndices[i];
        const FString& AnchorName = Config.ParkingAnchors[SlotIndex];

        // Cycle through vehicle configs
        const FVehicleSpawnConfig& VehicleConfig = VehicleConfigs[i % VehicleConfigs.Num()];

        // Randomly choose parking mode
        EParkingMode Mode = Random.RandBool(Config.ReverseParkingProbability)
            ? EParkingMode::ReverseIn
            : EParkingMode::PullIn;

        FSpawnResult Result = SpawnAtParkingSlot(AnchorName, VehicleConfig, Mode);
        Results.Add(Result);

        if (Result.bSuccess)
        {
            SpawnedCount++;
        }
    }

    LogInfo(TEXT("ParkingSpawner"), TEXT("Parking spawn complete"),
        {
            {TEXT("requested"), FString::FromInt(VehiclesToSpawn)},
            {TEXT("spawned"), FString::FromInt(SpawnedCount)},
            {TEXT("failed"), FString::FromInt(VehiclesToSpawn - SpawnedCount)}
        });

    return Results;
}

FSpawnResult UAnchorSpawnSystem::SpawnAtParkingSlot(
    const FString& AnchorName,
    const FVehicleSpawnConfig& Config,
    EParkingMode Mode)
{
    FSpawnResult Result;
    Result.AnchorName = AnchorName;

    // Find anchor
    FAnchorDefinition* Anchor = ResolvedAnchors.Find(AnchorName);
    if (!Anchor || !Anchor->bIsValid)
    {
        Result.FailureReason = FString::Printf(TEXT("Anchor '%s' not found or invalid"), *AnchorName);
        LogError(TEXT("ParkingSpawner"), TEXT("Spawn failed"), Result.FailureReason);
        return Result;
    }

    // Compute transform
    FTransform SpawnTransform = ComputeParkingTransform(*Anchor, Mode);

    // Check for overlap with existing vehicles
    FVector VehicleExtent(250.0f, 100.0f, 75.0f); // Approximate car half-extents
    if (CheckOverlap(SpawnTransform, VehicleExtent))
    {
        Result.FailureReason = TEXT("Overlap with existing vehicle");
        LogError(TEXT("ParkingSpawner"), TEXT("Spawn failed"), Result.FailureReason);
        return Result;
    }

    // Generate instance ID
    Result.InstanceId = GenerateInstanceId(TEXT("parking"));

    // Spawn actor
    Result.SpawnedActor = SpawnActorFromAsset(Config.AssetPath, SpawnTransform, Result.InstanceId);

    if (Result.SpawnedActor)
    {
        Result.SpawnedActor->SetActorScale3D(FVector(Config.Scale));
        Result.FinalTransform = SpawnTransform;
        Result.bSuccess = true;

        SpawnedActors.Add(Result.SpawnedActor);
        LogSpawnResult(Result);
    }
    else
    {
        Result.FailureReason = TEXT("Actor spawn failed");
    }

    return Result;
}

FTransform UAnchorSpawnSystem::ComputeParkingTransform(const FAnchorDefinition& Anchor, EParkingMode Mode)
{
    FVector Location = Anchor.CachedTransform.GetLocation();
    FRotator Rotation = Anchor.CachedTransform.Rotator();

    // Apply position jitter
    float JitterX = Random.FRandRange(-Config.ParkingPositionJitter, Config.ParkingPositionJitter);
    float JitterY = Random.FRandRange(-Config.ParkingPositionJitter, Config.ParkingPositionJitter);
    Location.X += JitterX;
    Location.Y += JitterY;

    // Apply parking mode rotation
    if (Mode == EParkingMode::ReverseIn)
    {
        Rotation.Yaw += 180.0f;
    }

    // Apply yaw jitter
    float YawJitter = Random.FRandRange(-Config.ParkingYawJitter, Config.ParkingYawJitter);
    Rotation.Yaw += YawJitter;

    // Normalize yaw to [-180, 180]
    Rotation.Yaw = FMath::Fmod(Rotation.Yaw + 180.0f, 360.0f) - 180.0f;

    LogInfo(TEXT("ParkingSpawner"), TEXT("Transform computed"),
        {
            {TEXT("anchor"), Anchor.ActorName},
            {TEXT("mode"), Mode == EParkingMode::ReverseIn ? TEXT("reverse") : TEXT("pull_in")},
            {TEXT("jitter_xy"), FString::Printf(TEXT("(%.1f, %.1f)"), JitterX, JitterY)},
            {TEXT("yaw_jitter"), FString::Printf(TEXT("%.1f"), YawJitter)},
            {TEXT("final_yaw"), FString::Printf(TEXT("%.1f"), Rotation.Yaw)}
        });

    return FTransform(Rotation, Location, FVector::OneVector);
}

// ============================================================================
// Lane Spawning
// ============================================================================

TArray<FSpawnResult> UAnchorSpawnSystem::SpawnLaneVehicles(
    const TArray<FVehicleSpawnConfig>& VehicleConfigs,
    int32 VehiclesPerLane)
{
    TArray<FSpawnResult> Results;

    if (VehicleConfigs.Num() == 0)
    {
        LogError(TEXT("LaneSpawner"), TEXT("No vehicle configs provided"), TEXT("VehicleConfigs array is empty"));
        return Results;
    }

    int32 ValidLanes = 0;
    for (const FLaneDefinition& Lane : Config.Lanes)
    {
        if (Lane.bIsValid) ValidLanes++;
    }

    LogInfo(TEXT("LaneSpawner"), TEXT("Spawning lane vehicles"),
        {
            {TEXT("valid_lanes"), FString::FromInt(ValidLanes)},
            {TEXT("vehicles_per_lane"), FString::FromInt(VehiclesPerLane)},
            {TEXT("seed"), FString::FromInt(Random.GetSeed())}
        });

    int32 VehicleIndex = 0;
    for (const FLaneDefinition& Lane : Config.Lanes)
    {
        if (!Lane.bIsValid)
        {
            LogError(TEXT("LaneSpawner"), TEXT("Skipping invalid lane"), Lane.LaneId);
            continue;
        }

        // Distribute vehicles along lane
        for (int32 i = 0; i < VehiclesPerLane; i++)
        {
            // Compute T position along lane (avoid ends)
            float T = (i + 1.0f) / (VehiclesPerLane + 1.0f);

            // Add some randomization to T
            T += Random.FRandRange(-0.1f, 0.1f);
            T = FMath::Clamp(T, 0.05f, 0.95f);

            const FVehicleSpawnConfig& VehicleConfig = VehicleConfigs[VehicleIndex % VehicleConfigs.Num()];

            FSpawnResult Result = SpawnAlongLane(Lane.LaneId, T, VehicleConfig);
            Results.Add(Result);

            VehicleIndex++;
        }
    }

    int32 SuccessCount = 0;
    for (const FSpawnResult& R : Results)
    {
        if (R.bSuccess) SuccessCount++;
    }

    LogInfo(TEXT("LaneSpawner"), TEXT("Lane spawn complete"),
        {
            {TEXT("total_attempted"), FString::FromInt(Results.Num())},
            {TEXT("spawned"), FString::FromInt(SuccessCount)},
            {TEXT("failed"), FString::FromInt(Results.Num() - SuccessCount)}
        });

    return Results;
}

FSpawnResult UAnchorSpawnSystem::SpawnAlongLane(
    const FString& LaneId,
    float T,
    const FVehicleSpawnConfig& VehicleConfig)
{
    FSpawnResult Result;
    Result.AnchorName = LaneId;

    // Find lane
    const FLaneDefinition* Lane = nullptr;
    for (const FLaneDefinition& L : Config.Lanes)
    {
        if (L.LaneId == LaneId)
        {
            Lane = &L;
            break;
        }
    }

    if (!Lane || !Lane->bIsValid)
    {
        Result.FailureReason = FString::Printf(TEXT("Lane '%s' not found or invalid"), *LaneId);
        LogError(TEXT("LaneSpawner"), TEXT("Spawn failed"), Result.FailureReason);
        return Result;
    }

    // Compute transform
    FTransform SpawnTransform = ComputeLaneTransform(*Lane, T);

    // Check overlap
    FVector VehicleExtent(250.0f, 100.0f, 75.0f);
    if (CheckOverlap(SpawnTransform, VehicleExtent))
    {
        Result.FailureReason = TEXT("Overlap with existing vehicle");
        LogError(TEXT("LaneSpawner"), TEXT("Spawn failed"), Result.FailureReason);
        return Result;
    }

    // Generate instance ID
    Result.InstanceId = GenerateInstanceId(TEXT("lane"));

    // Spawn actor
    Result.SpawnedActor = SpawnActorFromAsset(VehicleConfig.AssetPath, SpawnTransform, Result.InstanceId);

    if (Result.SpawnedActor)
    {
        Result.SpawnedActor->SetActorScale3D(FVector(VehicleConfig.Scale));
        Result.FinalTransform = SpawnTransform;
        Result.bSuccess = true;

        SpawnedActors.Add(Result.SpawnedActor);
        LogSpawnResult(Result);
    }
    else
    {
        Result.FailureReason = TEXT("Actor spawn failed");
    }

    return Result;
}

FTransform UAnchorSpawnSystem::ComputeLaneTransform(const FLaneDefinition& Lane, float T)
{
    // Interpolate position along lane
    FVector StartLoc = Lane.StartTransform.GetLocation();
    FVector EndLoc = Lane.EndTransform.GetLocation();
    FVector Location = FMath::Lerp(StartLoc, EndLoc, T);

    // Compute yaw from lane direction
    FRotator Rotation = Lane.Direction.Rotation();

    // Apply lateral offset (perpendicular to lane direction)
    FVector Right = FVector::CrossProduct(Lane.Direction, FVector::UpVector).GetSafeNormal();
    float LateralOffset = Random.FRandRange(-Config.LaneLateralJitter, Config.LaneLateralJitter);
    Location += Right * LateralOffset;

    // Apply yaw jitter
    float YawJitter = Random.FRandRange(-Config.LaneYawJitter, Config.LaneYawJitter);
    Rotation.Yaw += YawJitter;

    LogInfo(TEXT("LaneSpawner"), TEXT("Transform computed"),
        {
            {TEXT("lane"), Lane.LaneId},
            {TEXT("t"), FString::Printf(TEXT("%.2f"), T)},
            {TEXT("lateral_offset"), FString::Printf(TEXT("%.1f"), LateralOffset)},
            {TEXT("yaw_jitter"), FString::Printf(TEXT("%.1f"), YawJitter)},
            {TEXT("final_yaw"), FString::Printf(TEXT("%.1f"), Rotation.Yaw)}
        });

    return FTransform(Rotation, Location, FVector::OneVector);
}

// ============================================================================
// Sidewalk Props
// ============================================================================

TArray<FSpawnResult> UAnchorSpawnSystem::SpawnSidewalkProps(
    const TArray<FString>& PropAssetPaths,
    int32 Count)
{
    TArray<FSpawnResult> Results;

    if (!Config.SidewalkBounds.bIsValid)
    {
        LogError(TEXT("SidewalkSpawner"), TEXT("Sidewalk bounds not valid"), TEXT("Ensure sidewalk anchors are resolved"));
        return Results;
    }

    if (PropAssetPaths.Num() == 0)
    {
        LogError(TEXT("SidewalkSpawner"), TEXT("No prop assets provided"), TEXT("PropAssetPaths is empty"));
        return Results;
    }

    LogInfo(TEXT("SidewalkSpawner"), TEXT("Spawning sidewalk props"),
        {
            {TEXT("count"), FString::FromInt(Count)},
            {TEXT("asset_types"), FString::FromInt(PropAssetPaths.Num())}
        });

    for (int32 i = 0; i < Count; i++)
    {
        FSpawnResult Result;
        Result.AnchorName = TEXT("SidewalkBounds");

        // Random position within bounds
        FVector Location = ComputeSidewalkPosition();

        // Ground alignment
        Location.Z = GetGroundZ(Location);

        // Random yaw rotation
        FRotator Rotation(0, Random.FRandRange(0, 360), 0);

        FTransform SpawnTransform(Rotation, Location, FVector::OneVector);

        // Random asset selection
        const FString& AssetPath = PropAssetPaths[Random.RandRange(0, PropAssetPaths.Num() - 1)];

        Result.InstanceId = GenerateInstanceId(TEXT("prop"));
        Result.SpawnedActor = SpawnActorFromAsset(AssetPath, SpawnTransform, Result.InstanceId);

        if (Result.SpawnedActor)
        {
            Result.FinalTransform = SpawnTransform;
            Result.bSuccess = true;
            SpawnedActors.Add(Result.SpawnedActor);
        }

        Results.Add(Result);
    }

    return Results;
}

FVector UAnchorSpawnSystem::ComputeSidewalkPosition()
{
    const FBox& Bounds = Config.SidewalkBounds.Bounds;

    float X = Random.FRandRange(Bounds.Min.X, Bounds.Max.X);
    float Y = Random.FRandRange(Bounds.Min.Y, Bounds.Max.Y);
    float Z = (Bounds.Min.Z + Bounds.Max.Z) * 0.5f; // Mid-point, will be adjusted by raycast

    return FVector(X, Y, Z);
}

float UAnchorSpawnSystem::GetGroundZ(const FVector& Location) const
{
    if (!World)
    {
        return Location.Z;
    }

    FHitResult HitResult;
    FVector Start = Location + FVector(0, 0, 500); // Start above
    FVector End = Location - FVector(0, 0, 1000);  // End below

    FCollisionQueryParams QueryParams;
    QueryParams.bTraceComplex = true;

    if (World->LineTraceSingleByChannel(HitResult, Start, End, ECC_WorldStatic, QueryParams))
    {
        return HitResult.ImpactPoint.Z;
    }

    return Location.Z;
}

// ============================================================================
// Cleanup
// ============================================================================

void UAnchorSpawnSystem::ClearAllSpawned()
{
    int32 Count = SpawnedActors.Num();

    for (AActor* Actor : SpawnedActors)
    {
        if (Actor && IsValid(Actor))
        {
            Actor->Destroy();
        }
    }

    SpawnedActors.Empty();
    InstanceCounter = 0;

    LogInfo(TEXT("AnchorSpawnSystem"), TEXT("Cleared all spawned actors"),
        {
            {TEXT("count"), FString::FromInt(Count)}
        });
}

// ============================================================================
// Collision Detection
// ============================================================================

bool UAnchorSpawnSystem::CheckOverlap(const FTransform& Transform, const FVector& VehicleExtent) const
{
    FVector NewLocation = Transform.GetLocation();

    for (AActor* ExistingActor : SpawnedActors)
    {
        if (!ExistingActor || !IsValid(ExistingActor))
        {
            continue;
        }

        FVector ExistingLocation = ExistingActor->GetActorLocation();
        float Distance = FVector::Dist2D(NewLocation, ExistingLocation);

        // Simple distance check (sum of extents)
        float MinDistance = VehicleExtent.X * 2.0f; // Approximate vehicle length

        if (Distance < MinDistance)
        {
            return true; // Overlap detected
        }
    }

    return false;
}

// ============================================================================
// Actor Spawning
// ============================================================================

AActor* UAnchorSpawnSystem::SpawnActorFromAsset(const FString& AssetPath, const FTransform& Transform, const FString& InstanceId)
{
    if (!World)
    {
        return nullptr;
    }

    // Try loading as blueprint class
    UClass* ActorClass = LoadClass<AActor>(nullptr, *AssetPath);

    if (ActorClass)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.Name = FName(*InstanceId);
        SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

        return World->SpawnActor<AActor>(
            ActorClass,
            Transform.GetLocation(),
            Transform.Rotator(),
            SpawnParams
        );
    }

    // Try loading as static mesh
    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *AssetPath);

    if (Mesh)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.Name = FName(*InstanceId);
        SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

        AActor* NewActor = World->SpawnActor<AActor>(
            AActor::StaticClass(),
            Transform.GetLocation(),
            Transform.Rotator(),
            SpawnParams
        );

        if (NewActor)
        {
            UStaticMeshComponent* MeshComp = NewObject<UStaticMeshComponent>(NewActor);
            MeshComp->SetStaticMesh(Mesh);
            MeshComp->RegisterComponent();
            NewActor->SetRootComponent(MeshComp);
        }

        return NewActor;
    }

    LogError(TEXT("AnchorSpawnSystem"), TEXT("Failed to load asset"),
        AssetPath,
        TEXT("Ensure asset path is valid and asset exists"));

    return nullptr;
}

FString UAnchorSpawnSystem::GenerateInstanceId(const FString& Prefix)
{
    return FString::Printf(TEXT("%s_%04d"), *Prefix, InstanceCounter++);
}

// ============================================================================
// Logging
// ============================================================================

void UAnchorSpawnSystem::LogInfo(const FString& Module, const FString& Message, const TMap<FString, FString>& Data)
{
    FString DataStr;
    for (const auto& Pair : Data)
    {
        if (!DataStr.IsEmpty())
        {
            DataStr += TEXT(", ");
        }
        DataStr += FString::Printf(TEXT("\"%s\": \"%s\""), *Pair.Key, *Pair.Value);
    }

    if (DataStr.IsEmpty())
    {
        UE_LOG(LogAnchorSpawn, Log, TEXT("[%s] %s"), *Module, *Message);
    }
    else
    {
        UE_LOG(LogAnchorSpawn, Log, TEXT("[%s] %s | {%s}"), *Module, *Message, *DataStr);
    }
}

void UAnchorSpawnSystem::LogError(const FString& Module, const FString& Message, const FString& Reason, const FString& SuggestedFix)
{
    if (SuggestedFix.IsEmpty())
    {
        UE_LOG(LogAnchorSpawn, Error, TEXT("[%s] %s | Reason: %s"), *Module, *Message, *Reason);
    }
    else
    {
        UE_LOG(LogAnchorSpawn, Error, TEXT("[%s] %s | Reason: %s | Fix: %s"),
            *Module, *Message, *Reason, *SuggestedFix);
    }
}

void UAnchorSpawnSystem::LogSpawnResult(const FSpawnResult& Result)
{
    if (Result.bSuccess)
    {
        FVector Loc = Result.FinalTransform.GetLocation();
        FRotator Rot = Result.FinalTransform.Rotator();

        LogInfo(TEXT("SpawnResult"), TEXT("Vehicle spawned"),
            {
                {TEXT("instance_id"), Result.InstanceId},
                {TEXT("anchor"), Result.AnchorName},
                {TEXT("location"), FString::Printf(TEXT("(%.1f, %.1f, %.1f)"), Loc.X, Loc.Y, Loc.Z)},
                {TEXT("rotation"), FString::Printf(TEXT("(%.1f, %.1f, %.1f)"), Rot.Pitch, Rot.Yaw, Rot.Roll)},
                {TEXT("seed"), FString::FromInt(Random.GetSeed())},
                {TEXT("rand_calls"), FString::FromInt(Random.GetCallCount())}
            });
    }
    else
    {
        LogError(TEXT("SpawnResult"), TEXT("Spawn failed"),
            Result.FailureReason,
            TEXT("Check anchor exists and no overlap"));
    }
}
