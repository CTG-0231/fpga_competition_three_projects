/* Application-owned standalone initialization for Vitis 2025.2 SDT BSPs. */
#include "xfc.h"

int XFc_Initialize(XFc *InstancePtr, UINTPTR BaseAddress)
{
    XFc_Config Config = { BaseAddress };
    return XFc_CfgInitialize(InstancePtr, &Config);
}
