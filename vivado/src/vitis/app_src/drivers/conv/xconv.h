// ==============================================================
// Vivado(TM) HLS - High-Level Synthesis from C, C++ and SystemC v2019.2 (64-bit)
// Copyright 1986-2019 Xilinx, Inc. All Rights Reserved.
// ==============================================================
#ifndef XCONV_H
#define XCONV_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
/* Standalone application driver: SDT BSPs supply types and MMIO helpers. */
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#include "xconv_hw.h"

/**************************** Type Definitions ******************************/
typedef struct {
    UINTPTR Ctrl_BaseAddress;
} XConv_Config;

typedef struct {
    UINTPTR Ctrl_BaseAddress;
    u32 IsReady;
} XConv;

/***************** Macros (Inline Functions) Definitions *********************/
#define XConv_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XConv_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))


/************************** Function Prototypes *****************************/
/* BaseAddress comes from the BSP xparameters.h through hw_config.h.
 * No legacy DeviceId or generated *_g.c configuration table is needed. */
int XConv_Initialize(XConv *InstancePtr, UINTPTR BaseAddress);
int XConv_CfgInitialize(XConv *InstancePtr, XConv_Config *ConfigPtr);

void XConv_Start(XConv *InstancePtr);
u32 XConv_IsDone(XConv *InstancePtr);
u32 XConv_IsIdle(XConv *InstancePtr);
u32 XConv_IsReady(XConv *InstancePtr);
void XConv_EnableAutoRestart(XConv *InstancePtr);
void XConv_DisableAutoRestart(XConv *InstancePtr);

void XConv_Set_in1_V(XConv *InstancePtr, u32 Data);
u32 XConv_Get_in1_V(XConv *InstancePtr);
void XConv_Set_in2_V(XConv *InstancePtr, u32 Data);
u32 XConv_Get_in2_V(XConv *InstancePtr);
void XConv_Set_in3_V(XConv *InstancePtr, u32 Data);
u32 XConv_Get_in3_V(XConv *InstancePtr);
void XConv_Set_weight_V(XConv *InstancePtr, u32 Data);
u32 XConv_Get_weight_V(XConv *InstancePtr);
void XConv_Set_bias_V(XConv *InstancePtr, u32 Data);
u32 XConv_Get_bias_V(XConv *InstancePtr);
void XConv_Set_out_V(XConv *InstancePtr, u32 Data);
u32 XConv_Get_out_V(XConv *InstancePtr);

void XConv_InterruptGlobalEnable(XConv *InstancePtr);
void XConv_InterruptGlobalDisable(XConv *InstancePtr);
void XConv_InterruptEnable(XConv *InstancePtr, u32 Mask);
void XConv_InterruptDisable(XConv *InstancePtr, u32 Mask);
void XConv_InterruptClear(XConv *InstancePtr, u32 Mask);
u32 XConv_InterruptGetEnabled(XConv *InstancePtr);
u32 XConv_InterruptGetStatus(XConv *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
