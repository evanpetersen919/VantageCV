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
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/SkyLight.h"
#include "Components/SkyLightComponent.h"

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
		// Use FINAL output - exactly what viewport shows
		CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
		CaptureComponent->bCaptureEveryFrame = false;
		CaptureComponent->bCaptureOnMovement = false;
		
		//==========================================================================
		// MATCH VIEWPORT OUTPUT
		//==========================================================================
		
		// Enable rendering features to match viewport
		CaptureComponent->ShowFlags.SetPostProcessing(true);
		CaptureComponent->ShowFlags.SetMotionBlur(false);
		CaptureComponent->ShowFlags.SetBloom(false);  // Disabled - use PPV setting
		CaptureComponent->ShowFlags.SetTemporalAA(false);  // Disabled - no temporal artifacts
		CaptureComponent->ShowFlags.SetAmbientOcclusion(true);
		CaptureComponent->ShowFlags.SetEyeAdaptation(false);  // CRITICAL: Disable auto-exposure here
		CaptureComponent->ShowFlags.SetAtmosphere(true);
		CaptureComponent->ShowFlags.SetSkyLighting(true);
		CaptureComponent->ShowFlags.SetLighting(true);
		CaptureComponent->ShowFlags.SetGlobalIllumination(true);
		CaptureComponent->ShowFlags.SetTonemapper(true);
		CaptureComponent->ShowFlags.SetColorGrading(true);
		
		// Use PostProcessVolume settings ONLY - no component overrides
		CaptureComponent->PostProcessBlendWeight = 0.0f;
		
		// NO OVERRIDES - PostProcessVolume_1 controls all settings
	}

	
	// Initialize scene center to zero (will be set in BeginPlay)
	SceneCenter = FVector::ZeroVector;
	InitialFOV = 90.0f;
}

void ADataCapture::BeginPlay()
{
	Super::BeginPlay();
	
	// Store initial position as scene center - camera will orbit around this point
	// Place your DataCapture actor WHERE YOUR VEHICLES ARE in the level
	SceneCenter = GetActorLocation();
	
	// Store initial FOV
	if (CaptureComponent)
	{
		InitialFOV = CaptureComponent->FOVAngle;
	}
	
	// Initialize default render targets
	SetResolution(1920, 1080);
	
	UE_LOG(LogDataCapture, Log, TEXT("DataCapture initialized - Scene Center: %s, FOV: %.1f"), 
		*SceneCenter.ToString(), InitialFOV);
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

	// Create RGB render target - use linear format (SCS_FinalColorLDR is already gamma-corrected)
	RenderTarget = NewObject<UTextureRenderTarget2D>(this);
	RenderTarget->RenderTargetFormat = RTF_RGBA8;  // Linear format for deterministic output
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
	UE_LOG(LogDataCapture, Log, TEXT("=== CaptureFrame START ==="));
	UE_LOG(LogDataCapture, Log, TEXT("Output: %s (%dx%d)"), *OutputPath, Width, Height);
	
	// Ensure CaptureComponent exists
	if (!CaptureComponent)
	{
		UE_LOG(LogDataCapture, Error, TEXT("CaptureComponent is null - this should never happen!"));
		return false;
	}
	
	//==========================================================================
	// VIEWPORT MATCH CONFIGURATION
	// Goal: Capture exactly what the viewport shows
	// Method: Use SCS_FinalColorLDR (viewport final output) with no overrides
	//==========================================================================
	
	// Capture configuration
	CaptureComponent->bCaptureEveryFrame = false;
	CaptureComponent->bCaptureOnMovement = false;
	CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;  // CRITICAL: Match viewport output
	
	// ShowFlags: Enable features but let PostProcessVolume control intensity/settings
	CaptureComponent->ShowFlags.SetPostProcessing(true);      // Required for PPV
	CaptureComponent->ShowFlags.SetLighting(true);            // Required for scene
	CaptureComponent->ShowFlags.SetTonemapper(true);          // Required for proper exposure
	CaptureComponent->ShowFlags.SetEyeAdaptation(false);      // CRITICAL: Disable auto-exposure
	CaptureComponent->ShowFlags.SetColorGrading(true);        // Let PPV control
	CaptureComponent->ShowFlags.SetBloom(true);               // Let PPV control (likely disabled in PPV)
	CaptureComponent->ShowFlags.SetAtmosphere(true);          // Atmosphere/fog
	CaptureComponent->ShowFlags.SetSkyLighting(true);         // Sky contribution
	CaptureComponent->ShowFlags.SetAmbientOcclusion(true);    // Let PPV control
	CaptureComponent->ShowFlags.SetGlobalIllumination(true);  // GI/Lumen
	CaptureComponent->ShowFlags.SetMotionBlur(false);         // Deterministic: no motion blur
	CaptureComponent->ShowFlags.SetTemporalAA(false);         // Deterministic: no temporal effects
	CaptureComponent->ShowFlags.SetGrain(false);              // Deterministic: no film grain
	CaptureComponent->ShowFlags.SetVignette(false);           // Deterministic: no vignette
	CaptureComponent->ShowFlags.SetScreenSpaceReflections(true);  // SSR for realism
	
	//==========================================================================
	// EXPOSURE CONTROL
	// SceneCaptureComponent2D does NOT automatically use world PostProcessVolume
	// BlendWeight=0 means "no post process" (causes bright/white output)
	// BlendWeight=1 means "use component's PostProcessSettings"
	// SOLUTION: Set explicit Manual Exposure on component with BlendWeight=1
	//==========================================================================
	CaptureComponent->PostProcessBlendWeight = 1.0f;
	CaptureComponent->bOverride_CustomNearClippingPlane = false;
	
	// Set MANUAL EXPOSURE to match what looks good in viewport
	CaptureComponent->PostProcessSettings.bOverride_AutoExposureMethod = true;
	CaptureComponent->PostProcessSettings.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
	CaptureComponent->PostProcessSettings.bOverride_AutoExposureBias = true;
	CaptureComponent->PostProcessSettings.AutoExposureBias = 0.0f;  // Neutral exposure - matches noon time state
	
	// Disable bloom and vignette for clean synthetic data
	CaptureComponent->PostProcessSettings.bOverride_BloomIntensity = true;
	CaptureComponent->PostProcessSettings.BloomIntensity = 0.0f;
	CaptureComponent->PostProcessSettings.bOverride_VignetteIntensity = true;
	CaptureComponent->PostProcessSettings.VignetteIntensity = 0.0f;
	CaptureComponent->PostProcessSettings.bOverride_SceneFringeIntensity = true;
	CaptureComponent->PostProcessSettings.SceneFringeIntensity = 0.0f;
	CaptureComponent->PostProcessSettings.bOverride_FilmGrainIntensity = true;
	CaptureComponent->PostProcessSettings.FilmGrainIntensity = 0.0f;
	CaptureComponent->PostProcessSettings.bOverride_MotionBlurAmount = true;
	CaptureComponent->PostProcessSettings.MotionBlurAmount = 0.0f;
	
	UE_LOG(LogDataCapture, Log, TEXT("Capture Config: Source=SCS_FinalColorLDR, BlendWeight=%.1f, Manual Exposure, Bias=%.1f"),
		CaptureComponent->PostProcessBlendWeight, CaptureComponent->PostProcessSettings.AutoExposureBias);

	// Create render target (RGBA8 linear for deterministic output)
	if (!RenderTarget || RenderTarget->SizeX != Width || RenderTarget->SizeY != Height)
	{
		UE_LOG(LogDataCapture, Log, TEXT("Creating render target %dx%d"), Width, Height);
		RenderTarget = NewObject<UTextureRenderTarget2D>(this);
		RenderTarget->RenderTargetFormat = RTF_RGBA8;  // Linear format (SCS_FinalColorLDR has gamma baked in)
		RenderTarget->ClearColor = FLinearColor::Black;
		RenderTarget->bAutoGenerateMips = false;
		RenderTarget->InitAutoFormat(Width, Height);
		RenderTarget->UpdateResourceImmediate(true);
	}
	
	// Assign render target to capture component
	CaptureComponent->TextureTarget = RenderTarget;
	
	// Log camera transform for debugging
	FVector ActorLoc = GetActorLocation();
	FRotator ActorRot = GetActorRotation();
	float FOV = CaptureComponent->FOVAngle;
	
	UE_LOG(LogDataCapture, Log, TEXT("Camera: Loc=(%.1f, %.1f, %.1f) Rot=(P:%.1f Y:%.1f R:%.1f) FOV=%.1f"),
		ActorLoc.X, ActorLoc.Y, ActorLoc.Z,
		ActorRot.Pitch, ActorRot.Yaw, ActorRot.Roll,
		FOV);

	// Capture the scene
	UE_LOG(LogDataCapture, Log, TEXT("Executing CaptureScene()..."));
	CaptureComponent->CaptureScene();
	
	// Wait for GPU to complete rendering (critical for deterministic output)
	FlushRenderingCommands();
	FRenderCommandFence Fence;
	Fence.BeginFence();
	Fence.Wait();
	
	UE_LOG(LogDataCapture, Log, TEXT("Render complete, writing to disk..."));

	// Save to file
	bool bSuccess = SaveRenderTargetToFile(RenderTarget, OutputPath);
	
	if (bSuccess)
	{
		UE_LOG(LogDataCapture, Log, TEXT("=== SUCCESS: %s (%dx%d) ==="), *OutputPath, Width, Height);
	}
	else
	{
		UE_LOG(LogDataCapture, Error, TEXT("=== FAILED: %s ==="), *OutputPath);
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
	// Use scene center as the target
	RandomizeCameraWithTarget(MinDistance, MaxDistance, MinFOV, MaxFOV, SceneCenter);
}

void ADataCapture::SetSceneCenter(FVector NewCenter)
{
	SceneCenter = NewCenter;
	UE_LOG(LogDataCapture, Log, TEXT("Scene center updated to: %s"), *SceneCenter.ToString());
}

void ADataCapture::RandomizeCameraWithTarget(float MinDistance, float MaxDistance, float MinFOV, float MaxFOV, FVector TargetPoint)
{
	if (!CaptureComponent) return;

	// Use provided target point, fall back to scene center if zero
	FVector LookTarget = TargetPoint;
	if (LookTarget.IsZero())
	{
		LookTarget = SceneCenter.IsZero() ? GetActorLocation() : SceneCenter;
		UE_LOG(LogDataCapture, Warning, TEXT("TargetPoint was zero, using fallback: %s"), *LookTarget.ToString());
	}

	// Random spherical coordinates for camera placement around TARGET
	// Distance is in centimeters (UE5 units)
	float Distance = FMath::RandRange(MinDistance, MaxDistance);
	float Theta = FMath::RandRange(0.0f, 360.0f);  // Azimuth (around target)
	float Phi = FMath::RandRange(15.0f, 60.0f);    // Elevation (15-60 degrees, realistic driving/surveillance angles)

	// Calculate offset from target using spherical coordinates
	FVector CameraOffset = FVector(
		Distance * FMath::Cos(FMath::DegreesToRadians(Theta)) * FMath::Cos(FMath::DegreesToRadians(Phi)),
		Distance * FMath::Sin(FMath::DegreesToRadians(Theta)) * FMath::Cos(FMath::DegreesToRadians(Phi)),
		Distance * FMath::Sin(FMath::DegreesToRadians(Phi))
	);

	// Final camera position = target + offset
	FVector CameraLocation = LookTarget + CameraOffset;

	// Look at target point (vehicle position)
	FRotator CameraRotation = (LookTarget - CameraLocation).Rotation();
	
	SetActorLocation(CameraLocation);
	SetActorRotation(CameraRotation);

	// Randomize FOV
	float RandomFOV = FMath::RandRange(MinFOV, MaxFOV);
	CaptureComponent->FOVAngle = RandomFOV;
	
	UE_LOG(LogDataCapture, Log, TEXT("Randomized camera - Target: %s, Location: %s, Distance: %.0f cm, FOV: %.1f"), 
		*LookTarget.ToString(), *CameraLocation.ToString(), Distance, RandomFOV);
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
	
	// Apply gamma correction when reading to brighten the output
	FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
	ReadFlags.SetLinearToGamma(true);  // Apply 2.2 gamma curve
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
	ReadPixelFlags.SetLinearToGamma(true);  // Apply gamma correction
	return RTResource->ReadPixels(OutPixels, ReadPixelFlags);
}
