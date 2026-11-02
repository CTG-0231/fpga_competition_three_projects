/* Application-owned standalone initialization for Vitis 2025.2 SDT BSPs. */
#include "xshortcut.h"

int XShortcut_Initialize(XShortcut *InstancePtr, UINTPTR BaseAddress)
{
    XShortcut_Config Config = { BaseAddress };
    return XShortcut_CfgInitialize(InstancePtr, &Config);
}
