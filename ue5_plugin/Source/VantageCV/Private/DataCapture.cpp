/******************************************************************************
 * VantageCV - Data Capture Implementation
 ******************************************************************************
 * File: DataCapture.cpp
 * Description: Implementation of image capture and annotation generation for
 *              synthetic computer vision datasets with ground truth extraction
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#include "DataCapture.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "ImageUtils.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Kismet/GameplayStatics.h"
#include "EngineUtils.h"
#include "Engine/Engine.h"
#include "Async/Async.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Json.h"
#include "JsonUtilities.h"
#include "RenderingThread.h"

DEFINE_LOG_CATEGORY_STATIC(LogDataCapture, Log, All);

ADataCapture::ADataCapture()
{
	PrimaryActorTick.bCanEverTick = true;

	// Create scene capture component
	CaptureComponent = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("SceneCaptureComponent"));
	RootComponent = CaptureComponent;

	// Configure capture settings
	if (CaptureComponent)
	{
		CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
		CaptureComponent->bCaptureEveryFrame = false;
		CaptureComponent->bCaptureOnMovement = false;
		
		// Enable post-processing but with fixed manual exposure for consistency
		CaptureComponent->ShowFlags.SetPostProcessing(true);
		CaptureComponent->ShowFlags.SetMotionBlur(false);
		CaptureComponent->ShowFlags.SetBloom(false);  // Disable bloom/glow
		CaptureComponent->ShowFlags.SetTemporalAA(false);
		CaptureComponent->ShowFlags.SetEyeAdaptation(false);  // Disable auto-exposure
		
		// Set manual exposure for consistent brightness across captures
		CaptureComponent->PostProcessSettings.bOverride_AutoExposureMethod = true;
		CaptureComponent->PostProcessSettings.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
		CaptureComponent->PostProcessSettings.bOverride_AutoExposureBias = true;
		CaptureComponent->PostProcessSettings.AutoExposureBias = 1.0f;  // Slight boost for indoor scenes
		
		// Explicitly disable bloom in post-process settings
		CaptureComponent->PostProcessSettings.bOverride_BloomIntensity = true;
		CaptureComponent->PostProcessSettings.BloomIntensity = 0.0f;
	}
}

void ADataCapture::BeginPlay()
{
	Super::BeginPlay();
	
	// Initialize default render targets
	SetResolution(1920, 1080);
	
	UE_LOG(LogDataCapture, Log, TEXT("DataCapture initialized with 1920x1080 resolution"));
}

void ADataCapture::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}

void ADataCapture::SetResolution(int32 Width, int32 Height)
{
	// Reuse existing render target if resolution matches
	if (RenderTarget && RenderTarget->SizeX == Width && RenderTarget->SizeY == Height)
	{
		UE_LOG(LogDataCapture, Log, TEXT("Render target already at %dx%d, reusing"), Width, Height);
		return;
	}

	// Create RGB render target with high-quality RGBA8 format
	RenderTarget = NewObject<UTextureRenderTarget2D>(this);
	RenderTarget->RenderTargetFormat = RTF_RGBA8;
	RenderTarget->ClearColor = FLinearColor::Black;
	RenderTarget->bAutoGenerateMips = false;
	RenderTarget->InitAutoFormat(Width, Height);
	RenderTarget->UpdateResourceImmediate(true);

	// Create segmentation render target
	SegmentationTarget = NewObject<UTextureRenderTarget2D>(this);
	SegmentationTarget->RenderTargetFormat = RTF_RGBA8;
	SegmentationTarget->ClearColor = FLinearColor::Black;
	SegmentationTarget->bAutoGenerateMips = false;
	SegmentationTarget->InitAutoFormat(Width, Height);
	SegmentationTarget->UpdateResourceImmediate(true);

	if (CaptureComponent)
	{
		CaptureComponent->TextureTarget = RenderTarget;
		CaptureComponent->bCaptureEveryFrame = false;
		CaptureComponent->bCaptureOnMovement = false;
	}

	UE_LOG(LogDataCapture, Log, TEXT("Set render resolution to %dx%d"), Width, Height);
}

bool ADataCapture::CaptureFrame(const FString& OutputPath, int32 Width, int32 Height)
{
	UE_LOG(LogDataCapture, Log, TEXT("CaptureFrame called: %s (%dx%d)"), *OutputPath, Width, Height);
	
	// Ensure CaptureComponent exists - use the one from constructor if available
	if (!CaptureComponent)
	{
		UE_LOG(LogDataCapture, Warning, TEXT("CaptureComponent was null, creating new one"));
		CaptureComponent = NewObject<USceneCaptureComponent2D>(this, TEXT("DataCaptureComponent"));
		CaptureComponent->RegisterComponent();
		CaptureComponent->AttachToComponent(GetRootComponent(), FAttachmentTransformRules::SnapToTargetIncludingScale);
	}
	
	// Configure capture settings
	CaptureComponent->bCaptureEveryFrame = false;
	CaptureComponent->bCaptureOnMovement = false;
	CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	CaptureComponent->ShowFlags.SetPostProcessing(true);
	CaptureComponent->ShowFlags.SetMotionBlur(false);
	CaptureComponent->ShowFlags.SetBloom(false);
	CaptureComponent->ShowFlags.SetTemporalAA(false);
	CaptureComponent->ShowFlags.SetEyeAdaptation(false);
	CaptureComponent->PostProcessSettings.bOverride_AutoExposureMethod = true;
	CaptureComponent->PostProcessSettings.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
	CaptureComponent->PostProcessSettings.bOverride_AutoExposureBias = true;
	CaptureComponent->PostProcessSettings.AutoExposureBias = 1.0f;
	CaptureComponent->PostProcessSettings.bOverride_BloomIntensity = true;
	CaptureComponent->PostProcessSettings.BloomIntensity = 0.0f;

	// Create or update render target
	if (!RenderTarget || RenderTarget->SizeX != Width || RenderTarget->SizeY != Height)
	{
		UE_LOG(LogDataCapture, Log, TEXT("Creating render target %dx%d"), Width, Height);
		RenderTarget = NewObject<UTextureRenderTarget2D>(this);
		RenderTarget->RenderTargetFormat = RTF_RGBA8;
		RenderTarget->ClearColor = FLinearColor::Black;
		RenderTarget->bAutoGenerateMips = false;
		RenderTarget->InitAutoFormat(Width, Height);
		RenderTarget->UpdateResourceImmediate(true);
	}
	
	// CRITICAL: Assign render target to capture component
	CaptureComponent->TextureTarget = RenderTarget;
	UE_LOG(LogDataCapture, Log, TEXT("TextureTarget assigned, size: %dx%d"), RenderTarget->SizeX, RenderTarget->SizeY);

	// Get camera position from editor viewport
	UWorld* World = GetWorld();
	if (World)
	{
		// Try to get the editor viewport camera
		for (FConstPlayerControllerIterator Iterator = World->GetPlayerControllerIterator(); Iterator; ++Iterator)
		{
			APlayerController* PC = Iterator->Get();
			if (PC && PC->PlayerCameraManager)
			{
				FVector CamLoc = PC->PlayerCameraManager->GetCameraLocation();
				FRotator CamRot = PC->PlayerCameraManager->GetCameraRotation();
				float FOV = PC->PlayerCameraManager->GetFOVAngle();
				
				SetActorLocation(CamLoc);
				SetActorRotation(CamRot);
				CaptureComponent->FOVAngle = FOV;
				
				UE_LOG(LogDataCapture, Log, TEXT("Camera: Loc=%s Rot=%s FOV=%.1f"), *CamLoc.ToString(), *CamRot.ToString(), FOV);
				break;
			}
		}
	}

	// Capture the scene
	UE_LOG(LogDataCapture, Log, TEXT("Calling CaptureScene()..."));
	CaptureComponent->CaptureScene();
	
	// Wait for render to complete
	FlushRenderingCommands();
	
	FRenderCommandFence Fence;
	Fence.BeginFence();
	Fence.Wait();
	
	UE_LOG(LogDataCapture, Log, TEXT("Render commands flushed, saving to file..."));

	// Save to file
	bool bSuccess = SaveRenderTargetToFile(RenderTarget, OutputPath);
	
	if (bSuccess)
	{
		UE_LOG(LogDataCapture, Log, TEXT("SUCCESS: Captured frame to: %s (%dx%d)"), *OutputPath, Width, Height);
	}
	else
	{
		UE_LOG(LogDataCapture, Error, TEXT("FAILED to save frame to: %s"), *OutputPath);
	}

	return bSuccess;
}

FString ADataCapture::GenerateBoundingBoxes(const TArray<FString>& TargetTags)
{
	TArray<AActor*> Actors = GetAnnotatableActors(TargetTags);
	TArray<TSharedPtr<FJsonValue>> AnnotationsArray;

	for (AActor* Actor : Actors)
	{
		if (!Actor) continue;

		FVector2D BBoxMin, BBoxMax;
		if (CalculateBoundingBox(Actor, BBoxMin, BBoxMax))
		{
			TSharedPtr<FJsonObject> AnnotationObj = MakeShareable(new FJsonObject);
			
			AnnotationObj->SetStringField("class", Actor->GetClass()->GetName());
			AnnotationObj->SetNumberField("x_min", BBoxMin.X);
			AnnotationObj->SetNumberField("y_min", BBoxMin.Y);
			AnnotationObj->SetNumberField("x_max", BBoxMax.X);
			AnnotationObj->SetNumberField("y_max", BBoxMax.Y);
			AnnotationObj->SetNumberField("width", BBoxMax.X - BBoxMin.X);
			AnnotationObj->SetNumberField("height", BBoxMax.Y - BBoxMin.Y);

			AnnotationsArray.Add(MakeShareable(new FJsonValueObject(AnnotationObj)));
		}
	}

	// Convert to JSON string
	TSharedPtr<FJsonObject> RootObj = MakeShareable(new FJsonObject);
	RootObj->SetArrayField("annotations", AnnotationsArray);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObj.ToSharedRef(), Writer);

	UE_LOG(LogDataCapture, Log, TEXT("Generated %d bounding box annotations"), AnnotationsArray.Num());
	return OutputString;
}

bool ADataCapture::GenerateSegmentationMask(const FString& OutputPath, int32 Width, int32 Height)
{
	if (!CaptureComponent || !SegmentationTarget)
	{
		UE_LOG(LogDataCapture, Error, TEXT("CaptureComponent or SegmentationTarget not initialized"));
		return false;
	}

	// Update resolution if needed
	if (SegmentationTarget->SizeX != Width || SegmentationTarget->SizeY != Height)
	{
		SegmentationTarget->InitAutoFormat(Width, Height);
		SegmentationTarget->UpdateResourceImmediate(true);
	}

	// Switch to segmentation rendering mode
	CaptureComponent->TextureTarget = SegmentationTarget;
	CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_SceneColorHDR;
	CaptureComponent->ShowFlags.SetPostProcessing(false);
	CaptureComponent->CaptureScene();

	// Save segmentation mask
	bool bSuccess = SaveRenderTargetToFile(SegmentationTarget, OutputPath);

	// Restore normal rendering
	CaptureComponent->TextureTarget = RenderTarget;
	CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	CaptureComponent->ShowFlags.SetPostProcessing(true);

	if (bSuccess)
	{
		UE_LOG(LogDataCapture, Log, TEXT("Generated segmentation mask: %s"), *OutputPath);
	}
	else
	{
		UE_LOG(LogDataCapture, Error, TEXT("Failed to generate segmentation mask: %s"), *OutputPath);
	}

	return bSuccess;
}

FString ADataCapture::GeneratePoseAnnotations(const TArray<FString>& TargetTags)
{
	TArray<AActor*> Actors = GetAnnotatableActors(TargetTags);
	TArray<TSharedPtr<FJsonValue>> PosesArray;

	for (AActor* Actor : Actors)
	{
		if (!Actor) continue;

		FVector Location = Actor->GetActorLocation();
		FRotator Rotation = Actor->GetActorRotation();
		FVector Scale = Actor->GetActorScale3D();

		TSharedPtr<FJsonObject> PoseObj = MakeShareable(new FJsonObject);
		
		PoseObj->SetStringField("class", Actor->GetClass()->GetName());
		
		// Translation
		TArray<TSharedPtr<FJsonValue>> TranslationArray;
		TranslationArray.Add(MakeShareable(new FJsonValueNumber(Location.X)));
		TranslationArray.Add(MakeShareable(new FJsonValueNumber(Location.Y)));
		TranslationArray.Add(MakeShareable(new FJsonValueNumber(Location.Z)));
		PoseObj->SetArrayField("translation", TranslationArray);

		// Rotation (Euler angles)
		TArray<TSharedPtr<FJsonValue>> RotationArray;
		RotationArray.Add(MakeShareable(new FJsonValueNumber(Rotation.Roll)));
		RotationArray.Add(MakeShareable(new FJsonValueNumber(Rotation.Pitch)));
		RotationArray.Add(MakeShareable(new FJsonValueNumber(Rotation.Yaw)));
		PoseObj->SetArrayField("rotation", RotationArray);

		// Scale
		TArray<TSharedPtr<FJsonValue>> ScaleArray;
		ScaleArray.Add(MakeShareable(new FJsonValueNumber(Scale.X)));
		ScaleArray.Add(MakeShareable(new FJsonValueNumber(Scale.Y)));
		ScaleArray.Add(MakeShareable(new FJsonValueNumber(Scale.Z)));
		PoseObj->SetArrayField("scale", ScaleArray);

		PosesArray.Add(MakeShareable(new FJsonValueObject(PoseObj)));
	}

	// Convert to JSON string
	TSharedPtr<FJsonObject> RootObj = MakeShareable(new FJsonObject);
	RootObj->SetArrayField("poses", PosesArray);

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(RootObj.ToSharedRef(), Writer);

	UE_LOG(LogDataCapture, Log, TEXT("Generated %d pose annotations"), PosesArray.Num());
	return OutputString;
}

TArray<AActor*> ADataCapture::GetAnnotatableActors(const TArray<FString>& FilterTags) const
{
	TArray<AActor*> FoundActors;
	UWorld* World = GetWorld();
	if (!World) return FoundActors;

	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		for (const FString& Tag : FilterTags)
		{
			if (Actor->ActorHasTag(FName(*Tag)))
			{
				FoundActors.Add(Actor);
				break;
			}
		}
	}

	return FoundActors;
}

bool ADataCapture::CalculateBoundingBox(AActor* Actor, FVector2D& OutMin, FVector2D& OutMax) const
{
	if (!Actor) return false;

	FVector Origin, BoxExtent;
	Actor->GetActorBounds(false, Origin, BoxExtent);

	// Get 8 corners of bounding box
	TArray<FVector> Corners;
	Corners.Add(Origin + FVector(BoxExtent.X, BoxExtent.Y, BoxExtent.Z));
	Corners.Add(Origin + FVector(BoxExtent.X, BoxExtent.Y, -BoxExtent.Z));
	Corners.Add(Origin + FVector(BoxExtent.X, -BoxExtent.Y, BoxExtent.Z));
	Corners.Add(Origin + FVector(BoxExtent.X, -BoxExtent.Y, -BoxExtent.Z));
	Corners.Add(Origin + FVector(-BoxExtent.X, BoxExtent.Y, BoxExtent.Z));
	Corners.Add(Origin + FVector(-BoxExtent.X, BoxExtent.Y, -BoxExtent.Z));
	Corners.Add(Origin + FVector(-BoxExtent.X, -BoxExtent.Y, BoxExtent.Z));
	Corners.Add(Origin + FVector(-BoxExtent.X, -BoxExtent.Y, -BoxExtent.Z));

	// Project to screen space
	float MinX = FLT_MAX, MinY = FLT_MAX;
	float MaxX = -FLT_MAX, MaxY = -FLT_MAX;

	for (const FVector& Corner : Corners)
	{
		FVector2D ScreenPos = ProjectWorldToScreen(Corner);
		MinX = FMath::Min(MinX, ScreenPos.X);
		MinY = FMath::Min(MinY, ScreenPos.Y);
		MaxX = FMath::Max(MaxX, ScreenPos.X);
		MaxY = FMath::Max(MaxY, ScreenPos.Y);
	}

	OutMin = FVector2D(MinX, MinY);
	OutMax = FVector2D(MaxX, MaxY);

	return true;
}

FVector2D ADataCapture::ProjectWorldToScreen(const FVector& WorldLocation) const
{
	UWorld* World = GetWorld();
	if (!World) return FVector2D::ZeroVector;

	APlayerController* PC = UGameplayStatics::GetPlayerController(World, 0);
	if (!PC) return FVector2D::ZeroVector;

	FVector2D ScreenLocation;
	PC->ProjectWorldLocationToScreen(WorldLocation, ScreenLocation);

	return ScreenLocation;
}

void ADataCapture::MatchViewportCamera()
{
	UWorld* World = GetWorld();
	if (!World || !CaptureComponent) return;

	APlayerCameraManager* CameraManager = UGameplayStatics::GetPlayerCameraManager(World, 0);
	if (CameraManager)
	{
		// Match camera transform
		FVector CamLocation = CameraManager->GetCameraLocation();
		FRotator CamRotation = CameraManager->GetCameraRotation();
		
		SetActorLocation(CamLocation);
		SetActorRotation(CamRotation);
		
		// Match FOV
		float CamFOV = CameraManager->GetFOVAngle();
		CaptureComponent->FOVAngle = CamFOV;
		
		UE_LOG(LogDataCapture, Log, TEXT("Matched viewport camera - Location: %s, Rotation: %s, FOV: %.2f"), 
			*CamLocation.ToString(), *CamRotation.ToString(), CamFOV);
	}
}

void ADataCapture::RandomizeCamera(float MinDistance, float MaxDistance, float MinFOV, float MaxFOV)
{
	if (!CaptureComponent) return;

	// Random spherical coordinates for camera placement around origin
	float Distance = FMath::RandRange(MinDistance, MaxDistance);
	float Theta = FMath::RandRange(0.0f, 360.0f);  // Azimuth (around object)
	float Phi = FMath::RandRange(30.0f, 80.0f);   // Elevation (overhead angles only, 90 = directly above)

	FVector CameraLocation = FVector(
		Distance * FMath::Cos(FMath::DegreesToRadians(Theta)) * FMath::Cos(FMath::DegreesToRadians(Phi)),
		Distance * FMath::Sin(FMath::DegreesToRadians(Theta)) * FMath::Cos(FMath::DegreesToRadians(Phi)),
		Distance * FMath::Sin(FMath::DegreesToRadians(Phi))
	);

	// Look at origin (where PCB is)
	FRotator CameraRotation = (FVector::ZeroVector - CameraLocation).Rotation();
	
	SetActorLocation(CameraLocation);
	SetActorRotation(CameraRotation);

	// Randomize FOV
	float RandomFOV = FMath::RandRange(MinFOV, MaxFOV);
	CaptureComponent->FOVAngle = RandomFOV;
	
	UE_LOG(LogDataCapture, Log, TEXT("Randomized camera - Location: %s, Rotation: %s, FOV: %.2f, Distance: %.2f"), 
		*CameraLocation.ToString(), *CameraRotation.ToString(), RandomFOV, Distance);
}

bool ADataCapture::SaveRenderTargetToFile(UTextureRenderTarget2D* InRenderTarget, const FString& FilePath)
{
	if (!InRenderTarget)
	{
		UE_LOG(LogDataCapture, Error, TEXT("SaveRenderTargetToFile: InRenderTarget is null"));
		return false;
	}

	UE_LOG(LogDataCapture, Log, TEXT("Saving render target to: %s"), *FilePath);

	// Ensure directory exists
	FString Directory = FPaths::GetPath(FilePath);
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
	if (!PlatformFile.DirectoryExists(*Directory))
	{
		UE_LOG(LogDataCapture, Log, TEXT("Creating directory: %s"), *Directory);
		PlatformFile.CreateDirectoryTree(*Directory);
	}

	// Use FImageUtils for reliable render target export
	FTextureRenderTargetResource* RTResource = InRenderTarget->GameThread_GetRenderTargetResource();
	if (!RTResource)
	{
		UE_LOG(LogDataCapture, Error, TEXT("Failed to get render target resource"));
		return false;
	}

	// Read pixels synchronously
	TArray<FColor> Pixels;
	Pixels.SetNum(InRenderTarget->SizeX * InRenderTarget->SizeY);
	
	UE_LOG(LogDataCapture, Log, TEXT("Reading %dx%d pixels..."), InRenderTarget->SizeX, InRenderTarget->SizeY);
	
	FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
	if (!RTResource->ReadPixels(Pixels, ReadFlags))
	{
		UE_LOG(LogDataCapture, Error, TEXT("Failed to read pixels from render target"));
		return false;
	}

	// Create image wrapper and save as PNG
	IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>(FName("ImageWrapper"));
	TSharedPtr<IImageWrapper> ImageWrapper = ImageWrapperModule.CreateImageWrapper(EImageFormat::PNG);
	
	if (ImageWrapper.IsValid() && ImageWrapper->SetRaw(Pixels.GetData(), Pixels.Num() * sizeof(FColor), 
		InRenderTarget->SizeX, InRenderTarget->SizeY, ERGBFormat::BGRA, 8))
	{
		const TArray64<uint8>& CompressedData = ImageWrapper->GetCompressed(100);
		if (FFileHelper::SaveArrayToFile(CompressedData, *FilePath))
		{
			UE_LOG(LogDataCapture, Log, TEXT("Successfully saved %lld bytes to: %s"), CompressedData.Num(), *FilePath);
			return true;
		}
		else
		{
			UE_LOG(LogDataCapture, Error, TEXT("FFileHelper::SaveArrayToFile failed for: %s"), *FilePath);
		}
	}
	else
	{
		UE_LOG(LogDataCapture, Error, TEXT("Image wrapper SetRaw or Compress failed"));
	}

	return false;
}

bool ADataCapture::ReadRenderTargetPixels(UTextureRenderTarget2D* InRenderTarget, TArray<FColor>& OutPixels)
{
	if (!InRenderTarget) return false;

	FTextureRenderTargetResource* RTResource = InRenderTarget->GameThread_GetRenderTargetResource();
	if (!RTResource) return false;

	OutPixels.SetNum(InRenderTarget->SizeX * InRenderTarget->SizeY);
	
	FReadSurfaceDataFlags ReadPixelFlags(RCM_UNorm);
	return RTResource->ReadPixels(OutPixels, ReadPixelFlags);
}
