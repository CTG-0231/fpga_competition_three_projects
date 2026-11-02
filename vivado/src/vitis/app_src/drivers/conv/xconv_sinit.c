/* Application-owned standalone initialization for Vitis 2025.2 SDT BSPs. */
#include "xconv.h"

int XConv_Initialize(XConv *InstancePtr, UINTPTR BaseAddress)
{
    XConv_Config Config = { BaseAddress };
    return XConv_CfgInitialize(InstancePtr, &Config);
}
