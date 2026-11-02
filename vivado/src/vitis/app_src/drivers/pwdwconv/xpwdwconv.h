// ==============================================================
// Vivado(TM) HLS - High-Level Synthesis from C, C++ and SystemC v2019.2 (64-bit)
// Copyright 1986-2019 Xilinx, Inc. All Rights Reserved.
// ==============================================================
#ifndef XPWDWCONV_H
#define XPWDWCONV_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
/* Standalone application driver: SDT BSPs supply types and MMIO helpers. */
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#include "xpwdwconv_hw.h"

/**************************** Type Definitions ******************************/
typedef struct {
    UINTPTR Ctrl_BaseAddress;
} XPwdwconv_Config;

typedef struct {
    UINTPTR Ctrl_BaseAddress;
    u32 IsReady;
} XPwdwconv;

/***************** Macros (Inline Functions) Definitions *********************/
#define XPwdwconv_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XPwdwconv_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))


/************************** Function Prototypes *****************************/
/* BaseAddress comes from the BSP xparameters.h through hw_config.h.
 * No legacy DeviceId or generated *_g.c configuration table is needed. */
int XPwdwconv_Initialize(XPwdwconv *InstancePtr, UINTPTR BaseAddress);
int XPwdwconv_CfgInitialize(XPwdwconv *InstancePtr, XPwdwconv_Config *ConfigPtr);

void XPwdwconv_Start(XPwdwconv *InstancePtr);
u32 XPwdwconv_IsDone(XPwdwconv *InstancePtr);
u32 XPwdwconv_IsIdle(XPwdwconv *InstancePtr);
u32 XPwdwconv_IsReady(XPwdwconv *InstancePtr);
void XPwdwconv_EnableAutoRestart(XPwdwconv *InstancePtr);
void XPwdwconv_DisableAutoRestart(XPwdwconv *InstancePtr);

void XPwdwconv_Set_PBUS1_V(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_PBUS1_V(XPwdwconv *InstancePtr);
void XPwdwconv_Set_PBUS2_V(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_PBUS2_V(XPwdwconv *InstancePtr);
void XPwdwconv_Set_PBUS3_V(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_PBUS3_V(XPwdwconv *InstancePtr);
void XPwdwconv_Set_PBUS4_V(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_PBUS4_V(XPwdwconv *InstancePtr);
void XPwdwconv_Set_SBUS1_V(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_SBUS1_V(XPwdwconv *InstancePtr);
void XPwdwconv_Set_SBUS2_V(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_SBUS2_V(XPwdwconv *InstancePtr);
void XPwdwconv_Set_ch_in(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_ch_in(XPwdwconv *InstancePtr);
void XPwdwconv_Set_ch_out(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_ch_out(XPwdwconv *InstancePtr);
void XPwdwconv_Set_stride(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_stride(XPwdwconv *InstancePtr);
void XPwdwconv_Set_fsize(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_fsize(XPwdwconv *InstancePtr);
void XPwdwconv_Set_act(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_act(XPwdwconv *InstancePtr);
void XPwdwconv_Set_mode(XPwdwconv *InstancePtr, u32 Data);
u32 XPwdwconv_Get_mode(XPwdwconv *InstancePtr);

void XPwdwconv_InterruptGlobalEnable(XPwdwconv *InstancePtr);
void XPwdwconv_InterruptGlobalDisable(XPwdwconv *InstancePtr);
void XPwdwconv_InterruptEnable(XPwdwconv *InstancePtr, u32 Mask);
void XPwdwconv_InterruptDisable(XPwdwconv *InstancePtr, u32 Mask);
void XPwdwconv_InterruptClear(XPwdwconv *InstancePtr, u32 Mask);
u32 XPwdwconv_InterruptGetEnabled(XPwdwconv *InstancePtr);
u32 XPwdwconv_InterruptGetStatus(XPwdwconv *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
