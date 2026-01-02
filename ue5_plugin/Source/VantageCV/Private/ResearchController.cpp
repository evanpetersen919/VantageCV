// Copyright VantageCV Research. All Rights Reserved.

#include "ResearchController.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "ImageUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformFilemanager.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Math/UnrealMathUtility.h"

DEFINE_LOG_CATEGORY_STATIC(LogResearchController, Log, All);

// Structured logging macro
#define RESEARCH_LOG(Module, Message, ...) \
    UE_LOG(LogResearchController, Log, TEXT("[%s] %s"), TEXT(#Module), *FString::Printf(TEXT(Message), ##__VA_ARGS__))

#define RESEARCH_LOG_ERROR(Module, Message, Reason) \
    UE_LOG(LogResearchController, Error, TEXT("[%s] %s | Reason: %s"), TEXT(#Module), TEXT(Message), TEXT(Reason))

AResearchController::AResearchController()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = false;

    // Set output directory default
    OutputDirectory = FPaths::ProjectSavedDir() / TEXT("Research");
}

void AResearchController::BeginPlay()
{
    Super::BeginPlay();

    SetupCaptureComponent();

    RESEARCH_LOG(ResearchController, "BeginPlay - Research Controller initialized");
}

void AResearchController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    ClearVehicles();
    Super::EndPlay(EndPlayReason);

    RESEARCH_LOG(ResearchController, "EndPlay - Research Controller destroyed");
}

void AResearchController::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
}

// ========================================
// MODULE 1: Scene Control
// ========================================

bool AResearchController::InitializeScene(const FString& SceneId, int32 Seed)
{
    LogInfo(TEXT("SceneController"), TEXT("Initializing scene"),
        {
            {TEXT("scene_id"), SceneId},
            {TEXT("seed"), FString::FromInt(Seed)}
        });

    CurrentSceneId = SceneId;
    CurrentSeed = Seed;
    FrameCounter = 0;
    bIsInitialized = true;

    // Seed random stream
    FMath::RandInit(Seed);

    // Clear any existing vehicles
    ClearVehicles();

    LogInfo(TEXT("SceneController"), TEXT("Scene initialized successfully"),
        {
            {TEXT("scene_id"), CurrentSceneId},
            {TEXT("is_initialized"), TEXT("true")}
        });

    return true;
}

void AResearchController::ResetScene(int32 NewSeed)
{
    if (NewSeed < 0)
    {
        NewSeed = CurrentSeed + 1;
    }

    LogInfo(TEXT("SceneController"), TEXT("Resetting scene"),
        {
            {TEXT("previous_seed"), FString::FromInt(CurrentSeed)},
            {TEXT("new_seed"), FString::FromInt(NewSeed)}
        });

    ClearVehicles();
    CurrentSeed = NewSeed;
    FrameCounter = 0;
    FMath::RandInit(NewSeed);
}

void AResearchController::SetTimeOfDay(bool bIsDay)
{
    bIsDaytime = bIsDay;

    LogInfo(TEXT("SceneController"), TEXT("Time of day changed"),
        {
            {TEXT("time"), bIsDay ? TEXT("day") : TEXT("night")}
        });

    // TODO: Implement lighting changes
    // This would typically adjust:
    // - Directional light intensity and angle
    // - Sky light
    // - Post-process settings
}

// ========================================
// MODULE 2: Vehicle Spawning
// ========================================

AActor* AResearchController::SpawnVehicle(const FResearchVehicleData& VehicleData)
{
    LogInfo(TEXT("VehicleSpawner"), TEXT("Spawn request received"),
        {
            {TEXT("instance_id"), VehicleData.InstanceId},
            {TEXT("class"), VehicleData.VehicleClass},
            {TEXT("asset_path"), VehicleData.AssetPath}
        });

    UWorld* World = GetWorld();
    if (!World)
    {
        LogError(TEXT("VehicleSpawner"), TEXT("Spawn failed"), TEXT("World is null"));
        return nullptr;
    }

    // Load vehicle mesh/blueprint
    UClass* VehicleClass = LoadClass<AActor>(nullptr, *VehicleData.AssetPath);
    
    AActor* SpawnedActor = nullptr;

    if (VehicleClass)
    {
        // Spawn from blueprint
        FActorSpawnParameters SpawnParams;
        SpawnParams.Name = FName(*VehicleData.InstanceId);
        SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

        SpawnedActor = World->SpawnActor<AActor>(
            VehicleClass,
            VehicleData.Location,
            VehicleData.Rotation,
            SpawnParams
        );
    }
    else
    {
        // Try loading as static mesh and spawn with mesh component
        UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *VehicleData.AssetPath);
        
        if (Mesh)
        {
            FActorSpawnParameters SpawnParams;
            SpawnParams.Name = FName(*VehicleData.InstanceId);
            SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

            SpawnedActor = World->SpawnActor<AActor>(
                AActor::StaticClass(),
                VehicleData.Location,
                VehicleData.Rotation,
                SpawnParams
            );

            if (SpawnedActor)
            {
                UStaticMeshComponent* MeshComp = NewObject<UStaticMeshComponent>(SpawnedActor);
                MeshComp->SetStaticMesh(Mesh);
                MeshComp->RegisterComponent();
                SpawnedActor->SetRootComponent(MeshComp);
            }
        }
        else
        {
            LogError(TEXT("VehicleSpawner"), TEXT("Spawn failed"), 
                TEXT("Could not load asset"),
                FString::Printf(TEXT("Check that asset exists at path: %s"), *VehicleData.AssetPath));
            return nullptr;
        }
    }

    if (SpawnedActor)
    {
        // Apply scale
        SpawnedActor->SetActorScale3D(FVector(VehicleData.Scale));

        // Store reference
        SpawnedVehicles.Add(SpawnedActor);
        VehicleInstanceMap.Add(VehicleData.InstanceId, SpawnedActor);

        LogInfo(TEXT("VehicleSpawner"), TEXT("Vehicle spawned successfully"),
            {
                {TEXT("instance_id"), VehicleData.InstanceId},
                {TEXT("class"), VehicleData.VehicleClass},
                {TEXT("location"), FString::Printf(TEXT("(%.1f, %.1f, %.1f)"), 
                    VehicleData.Location.X, VehicleData.Location.Y, VehicleData.Location.Z)},
                {TEXT("scale"), FString::Printf(TEXT("%.2f"), VehicleData.Scale)}
            });
    }
    else
    {
        LogError(TEXT("VehicleSpawner"), TEXT("Spawn failed"), TEXT("Actor creation failed"));
    }

    return SpawnedActor;
}

int32 AResearchController::SpawnVehicles(const TArray<FResearchVehicleData>& Vehicles)
{
    LogInfo(TEXT("VehicleSpawner"), TEXT("Batch spawn request"),
        {
            {TEXT("count"), FString::FromInt(Vehicles.Num())}
        });

    int32 SuccessCount = 0;

    for (const FResearchVehicleData& VehicleData : Vehicles)
    {
        AActor* Spawned = SpawnVehicle(VehicleData);
        if (Spawned)
        {
            SuccessCount++;
        }
    }

    LogInfo(TEXT("VehicleSpawner"), TEXT("Batch spawn completed"),
        {
            {TEXT("requested"), FString::FromInt(Vehicles.Num())},
            {TEXT("spawned"), FString::FromInt(SuccessCount)},
            {TEXT("failed"), FString::FromInt(Vehicles.Num() - SuccessCount)}
        });

    return SuccessCount;
}

void AResearchController::ClearVehicles()
{
    int32 Count = SpawnedVehicles.Num();

    for (AActor* Vehicle : SpawnedVehicles)
    {
        if (Vehicle && IsValid(Vehicle))
        {
            Vehicle->Destroy();
        }
    }

    SpawnedVehicles.Empty();
    VehicleInstanceMap.Empty();

    LogInfo(TEXT("VehicleSpawner"), TEXT("Vehicles cleared"),
        {
            {TEXT("count"), FString::FromInt(Count)}
        });
}

// ========================================
// MODULE 3: Camera Control
// ========================================

void AResearchController::SetupCaptureComponent()
{
    // Create scene capture component
    CaptureComponent = NewObject<USceneCaptureComponent2D>(this);
    CaptureComponent->RegisterComponent();
    CaptureComponent->AttachToComponent(GetRootComponent(), FAttachmentTransformRules::KeepRelativeTransform);

    // Default settings
    CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
    CaptureComponent->bCaptureEveryFrame = false;
    CaptureComponent->bCaptureOnMovement = false;

    // Create initial render target
    UpdateRenderTarget(CameraConfig.Width, CameraConfig.Height);

    LogInfo(TEXT("CameraSystem"), TEXT("Capture component initialized"),
        {
            {TEXT("width"), FString::FromInt(CameraConfig.Width)},
            {TEXT("height"), FString::FromInt(CameraConfig.Height)},
            {TEXT("fov"), FString::Printf(TEXT("%.1f"), CameraConfig.FOV)}
        });
}

void AResearchController::UpdateRenderTarget(int32 Width, int32 Height)
{
    if (RenderTarget && RenderTarget->SizeX == Width && RenderTarget->SizeY == Height)
    {
        return; // No change needed
    }

    RenderTarget = NewObject<UTextureRenderTarget2D>(this);
    RenderTarget->InitCustomFormat(Width, Height, PF_B8G8R8A8, false);
    RenderTarget->UpdateResourceImmediate();

    if (CaptureComponent)
    {
        CaptureComponent->TextureTarget = RenderTarget;
    }

    LogInfo(TEXT("CameraSystem"), TEXT("Render target updated"),
        {
            {TEXT("width"), FString::FromInt(Width)},
            {TEXT("height"), FString::FromInt(Height)}
        });
}

void AResearchController::ConfigureCamera(const FResearchCameraConfig& Config)
{
    CameraConfig = Config;

    if (CaptureComponent)
    {
        CaptureComponent->SetWorldLocation(Config.Location);
        CaptureComponent->SetWorldRotation(Config.Rotation);
        CaptureComponent->FOVAngle = Config.FOV;
    }

    UpdateRenderTarget(Config.Width, Config.Height);

    // Compute and log intrinsics
    float FocalLengthPx = Config.Width / (2.0f * FMath::Tan(FMath::DegreesToRadians(Config.FOV / 2.0f)));

    LogInfo(TEXT("CameraSystem"), TEXT("Camera configured"),
        {
            {TEXT("location"), FString::Printf(TEXT("(%.1f, %.1f, %.1f)"),
                Config.Location.X, Config.Location.Y, Config.Location.Z)},
            {TEXT("rotation"), FString::Printf(TEXT("(%.1f, %.1f, %.1f)"),
                Config.Rotation.Pitch, Config.Rotation.Yaw, Config.Rotation.Roll)},
            {TEXT("fov"), FString::Printf(TEXT("%.1f"), Config.FOV)},
            {TEXT("fx"), FString::Printf(TEXT("%.2f"), FocalLengthPx)},
            {TEXT("fy"), FString::Printf(TEXT("%.2f"), FocalLengthPx)},
            {TEXT("cx"), FString::Printf(TEXT("%.1f"), Config.Width / 2.0f)},
            {TEXT("cy"), FString::Printf(TEXT("%.1f"), Config.Height / 2.0f)}
        });
}

// ========================================
// MODULE 4: Render & Capture
// ========================================

FResearchFrameResult AResearchController::CaptureFrame(int32 FrameIndex, const FString& OutputPath)
{
    FResearchFrameResult Result;
    Result.FrameIndex = FrameIndex;

    double StartTime = FPlatformTime::Seconds();

    LogInfo(TEXT("RenderCapture"), TEXT("Frame render start"),
        {
            {TEXT("frame_index"), FString::FromInt(FrameIndex)}
        });

    if (!CaptureComponent || !RenderTarget)
    {
        LogError(TEXT("RenderCapture"), TEXT("Capture failed"), TEXT("Capture component or render target not initialized"));
        return Result;
    }

    // Capture the scene
    CaptureComponent->CaptureScene();

    // Save to disk
    if (SaveRenderTargetToDisk(OutputPath))
    {
        Result.bSuccess = true;
        Result.ImagePath = OutputPath;
    }
    else
    {
        LogError(TEXT("RenderCapture"), TEXT("Save failed"), TEXT("Could not save render target to disk"));
    }

    double EndTime = FPlatformTime::Seconds();
    Result.RenderTimeMs = (EndTime - StartTime) * 1000.0f;

    LogInfo(TEXT("RenderCapture"), TEXT("Frame render complete"),
        {
            {TEXT("frame_index"), FString::FromInt(FrameIndex)},
            {TEXT("success"), Result.bSuccess ? TEXT("true") : TEXT("false")},
            {TEXT("image_path"), Result.ImagePath},
            {TEXT("render_time_ms"), FString::Printf(TEXT("%.2f"), Result.RenderTimeMs)}
        });

    FrameCounter++;
    return Result;
}

void AResearchController::SetOutputDirectory(const FString& Path)
{
    OutputDirectory = Path;

    // Create directory if it doesn't exist
    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
    if (!PlatformFile.DirectoryExists(*Path))
    {
        PlatformFile.CreateDirectoryTree(*Path);
    }

    LogInfo(TEXT("RenderCapture"), TEXT("Output directory set"),
        {
            {TEXT("path"), Path}
        });
}

bool AResearchController::SaveRenderTargetToDisk(const FString& FilePath)
{
    if (!RenderTarget)
    {
        return false;
    }

    FTextureRenderTargetResource* Resource = RenderTarget->GameThread_GetRenderTargetResource();
    if (!Resource)
    {
        return false;
    }

    // Read pixels
    TArray<FColor> Pixels;
    Pixels.SetNumUninitialized(CameraConfig.Width * CameraConfig.Height);

    FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
    Resource->ReadPixels(Pixels, ReadFlags);

    // Compress to PNG
    IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
    TSharedPtr<IImageWrapper> ImageWrapper = ImageWrapperModule.CreateImageWrapper(EImageFormat::PNG);

    if (!ImageWrapper->SetRaw(Pixels.GetData(), Pixels.Num() * sizeof(FColor),
        CameraConfig.Width, CameraConfig.Height, ERGBFormat::BGRA, 8))
    {
        return false;
    }

    // Get compressed data
    TArray64<uint8> CompressedData = ImageWrapper->GetCompressed(100);
    if (CompressedData.Num() == 0)
    {
        return false;
    }

    // Ensure directory exists
    FString Directory = FPaths::GetPath(FilePath);
    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
    if (!PlatformFile.DirectoryExists(*Directory))
    {
        PlatformFile.CreateDirectoryTree(*Directory);
    }

    // Write to file
    return FFileHelper::SaveArrayToFile(CompressedData, *FilePath);
}

// ========================================
// MODULE 5: Annotation Support
// ========================================

bool AResearchController::GetVehicleBounds(AActor* VehicleActor, FVector& OutCenter, FVector& OutExtent) const
{
    if (!VehicleActor || !IsValid(VehicleActor))
    {
        return false;
    }

    FBox Bounds = VehicleActor->GetComponentsBoundingBox();
    if (!Bounds.IsValid)
    {
        return false;
    }

    OutCenter = Bounds.GetCenter();
    OutExtent = Bounds.GetExtent();
    return true;
}

TArray<FString> AResearchController::GetAllVehicleBoundsJSON() const
{
    TArray<FString> Results;

    for (const auto& Pair : VehicleInstanceMap)
    {
        FVector Center, Extent;
        if (GetVehicleBounds(Pair.Value, Center, Extent))
        {
            // Format as JSON for easy parsing in Python
            FString Json = FString::Printf(
                TEXT("{\"instance_id\": \"%s\", \"center\": {\"x\": %.2f, \"y\": %.2f, \"z\": %.2f}, "
                     "\"extent\": {\"x\": %.2f, \"y\": %.2f, \"z\": %.2f}}"),
                *Pair.Key,
                Center.X, Center.Y, Center.Z,
                Extent.X, Extent.Y, Extent.Z
            );
            Results.Add(Json);
        }
    }

    return Results;
}

// ========================================
// Logging
// ========================================

void AResearchController::LogInfo(const FString& Module, const FString& Message, const TMap<FString, FString>& Data)
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
        UE_LOG(LogResearchController, Log, TEXT("[%s] %s"), *Module, *Message);
    }
    else
    {
        UE_LOG(LogResearchController, Log, TEXT("[%s] %s | {%s}"), *Module, *Message, *DataStr);
    }
}

void AResearchController::LogError(const FString& Module, const FString& Message, const FString& Reason, const FString& SuggestedFix)
{
    if (SuggestedFix.IsEmpty())
    {
        UE_LOG(LogResearchController, Error, TEXT("[%s] %s | Reason: %s"), *Module, *Message, *Reason);
    }
    else
    {
        UE_LOG(LogResearchController, Error, TEXT("[%s] %s | Reason: %s | Suggested fix: %s"),
            *Module, *Message, *Reason, *SuggestedFix);
    }
}
