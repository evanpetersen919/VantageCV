/******************************************************************************
 * VantageCV - Plugin Module Header
 ******************************************************************************
 * File: VantageCVModule.h
 * Description: Main module interface for VantageCV plugin, handles plugin
 *              initialization and Remote Control API registration
 * Author: Evan Petersen
 * Date: December 2025
 *****************************************************************************/

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

/**
 * VantageCV plugin module
 * Manages plugin lifecycle and Remote Control API endpoint registration
 */
class FVantageCVModule : public IModuleInterface
{
public:
	/** IModuleInterface implementation */
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

private:
	/** Register Remote Control API endpoints for Python communication */
	void RegisterRemoteControlEndpoints();
	
	/** Unregister Remote Control API endpoints */
	void UnregisterRemoteControlEndpoints();
};
