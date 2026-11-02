// ==============================================================
// Vivado(TM) HLS - High-Level Synthesis from C, C++ and SystemC v2019.2 (64-bit)
// Copyright 1986-2019 Xilinx, Inc. All Rights Reserved.
// ==============================================================
#ifndef XFC_H
#define XFC_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
/* Standalone application driver: SDT BSPs supply types and MMIO helpers. */
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#include "xfc_hw.h"

/**************************** Type Definitions ******************************/
typedef struct {
    UINTPTR Ctrl_BaseAddress;
} XFc_Config;

typedef struct {
    UINTPTR Ctrl_BaseAddress;
    u32 IsReady;
} XFc;

/***************** Macros (Inline Functions) Definitions *********************/
#define XFc_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XFc_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))


/************************** Function Prototypes *****************************/
/* BaseAddress comes from the BSP xparameters.h through hw_config.h.
 * No legacy DeviceId or generated *_g.c configuration table is needed. */
int XFc_Initialize(XFc *InstancePtr, UINTPTR BaseAddress);
int XFc_CfgInitialize(XFc *InstancePtr, XFc_Config *ConfigPtr);

void XFc_Start(XFc *InstancePtr);
u32 XFc_IsDone(XFc *InstancePtr);
u32 XFc_IsIdle(XFc *InstancePtr);
u32 XFc_IsReady(XFc *InstancePtr);
void XFc_EnableAutoRestart(XFc *InstancePtr);
void XFc_DisableAutoRestart(XFc *InstancePtr);

void XFc_Set_in_V(XFc *InstancePtr, u32 Data);
u32 XFc_Get_in_V(XFc *InstancePtr);
void XFc_Set_weight_V(XFc *InstancePtr, u32 Data);
u32 XFc_Get_weight_V(XFc *InstancePtr);
void XFc_Set_bias_V(XFc *InstancePtr, u32 Data);
u32 XFc_Get_bias_V(XFc *InstancePtr);
void XFc_Set_out_V(XFc *InstancePtr, u32 Data);
u32 XFc_Get_out_V(XFc *InstancePtr);

void XFc_InterruptGlobalEnable(XFc *InstancePtr);
void XFc_InterruptGlobalDisable(XFc *InstancePtr);
void XFc_InterruptEnable(XFc *InstancePtr, u32 Mask);
void XFc_InterruptDisable(XFc *InstancePtr, u32 Mask);
void XFc_InterruptClear(XFc *InstancePtr, u32 Mask);
u32 XFc_InterruptGetEnabled(XFc *InstancePtr);
u32 XFc_InterruptGetStatus(XFc *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
