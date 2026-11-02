// ==============================================================
// Vivado(TM) HLS - High-Level Synthesis from C, C++ and SystemC v2019.2 (64-bit)
// Copyright 1986-2019 Xilinx, Inc. All Rights Reserved.
// ==============================================================
#ifndef XSHORTCUT_H
#define XSHORTCUT_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
/* Standalone application driver: SDT BSPs supply types and MMIO helpers. */
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#include "xshortcut_hw.h"

/**************************** Type Definitions ******************************/
typedef struct {
    UINTPTR Ctrl_BaseAddress;
} XShortcut_Config;

typedef struct {
    UINTPTR Ctrl_BaseAddress;
    u32 IsReady;
} XShortcut;

/***************** Macros (Inline Functions) Definitions *********************/
#define XShortcut_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XShortcut_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))


/************************** Function Prototypes *****************************/
/* BaseAddress comes from the BSP xparameters.h through hw_config.h.
 * No legacy DeviceId or generated *_g.c configuration table is needed. */
int XShortcut_Initialize(XShortcut *InstancePtr, UINTPTR BaseAddress);
int XShortcut_CfgInitialize(XShortcut *InstancePtr, XShortcut_Config *ConfigPtr);

void XShortcut_Start(XShortcut *InstancePtr);
u32 XShortcut_IsDone(XShortcut *InstancePtr);
u32 XShortcut_IsIdle(XShortcut *InstancePtr);
u32 XShortcut_IsReady(XShortcut *InstancePtr);
void XShortcut_EnableAutoRestart(XShortcut *InstancePtr);
void XShortcut_DisableAutoRestart(XShortcut *InstancePtr);

void XShortcut_Set_src1_V(XShortcut *InstancePtr, u32 Data);
u32 XShortcut_Get_src1_V(XShortcut *InstancePtr);
void XShortcut_Set_src2_V(XShortcut *InstancePtr, u32 Data);
u32 XShortcut_Get_src2_V(XShortcut *InstancePtr);
void XShortcut_Set_dest_V(XShortcut *InstancePtr, u32 Data);
u32 XShortcut_Get_dest_V(XShortcut *InstancePtr);
void XShortcut_Set_length_r(XShortcut *InstancePtr, u32 Data);
u32 XShortcut_Get_length_r(XShortcut *InstancePtr);

void XShortcut_InterruptGlobalEnable(XShortcut *InstancePtr);
void XShortcut_InterruptGlobalDisable(XShortcut *InstancePtr);
void XShortcut_InterruptEnable(XShortcut *InstancePtr, u32 Mask);
void XShortcut_InterruptDisable(XShortcut *InstancePtr, u32 Mask);
void XShortcut_InterruptClear(XShortcut *InstancePtr, u32 Mask);
u32 XShortcut_InterruptGetEnabled(XShortcut *InstancePtr);
u32 XShortcut_InterruptGetStatus(XShortcut *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
