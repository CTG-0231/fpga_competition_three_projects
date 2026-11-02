/* Application-owned standalone initialization for Vitis 2025.2 SDT BSPs. */
#include "xpwdwconv.h"

int XPwdwconv_Initialize(XPwdwconv *InstancePtr, UINTPTR BaseAddress)
{
    XPwdwconv_Config Config = { BaseAddress };
    return XPwdwconv_CfgInitialize(InstancePtr, &Config);
}
