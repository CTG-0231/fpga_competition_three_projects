// ==============================================================
// Vivado(TM) HLS - High-Level Synthesis from C, C++ and SystemC v2019.2 (64-bit)
// Copyright 1986-2019 Xilinx, Inc. All Rights Reserved.
// ==============================================================
/***************************** Include Files *********************************/
#include "xshortcut.h"

/************************** Function Implementation *************************/
int XShortcut_CfgInitialize(XShortcut *InstancePtr, XShortcut_Config *ConfigPtr) {
    if (InstancePtr == NULL) {
        return XST_INVALID_PARAM;
    }
    InstancePtr->IsReady = 0U;
    if ((ConfigPtr == NULL) || (ConfigPtr->Ctrl_BaseAddress == (UINTPTR)0U) ||
        ((ConfigPtr->Ctrl_BaseAddress & (UINTPTR)3U) != 0U)) {
        return XST_INVALID_PARAM;
    }

    InstancePtr->Ctrl_BaseAddress = ConfigPtr->Ctrl_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}

void XShortcut_Start(XShortcut *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_AP_CTRL) & 0x80;
    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XShortcut_IsDone(XShortcut *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XShortcut_IsIdle(XShortcut *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XShortcut_IsReady(XShortcut *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XShortcut_EnableAutoRestart(XShortcut *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_AP_CTRL, 0x80);
}

void XShortcut_DisableAutoRestart(XShortcut *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_AP_CTRL, 0);
}

void XShortcut_Set_src1_V(XShortcut *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_SRC1_V_DATA, Data);
}

u32 XShortcut_Get_src1_V(XShortcut *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_SRC1_V_DATA);
    return Data;
}

void XShortcut_Set_src2_V(XShortcut *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_SRC2_V_DATA, Data);
}

u32 XShortcut_Get_src2_V(XShortcut *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_SRC2_V_DATA);
    return Data;
}

void XShortcut_Set_dest_V(XShortcut *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_DEST_V_DATA, Data);
}

u32 XShortcut_Get_dest_V(XShortcut *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_DEST_V_DATA);
    return Data;
}

void XShortcut_Set_length_r(XShortcut *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_LENGTH_R_DATA, Data);
}

u32 XShortcut_Get_length_r(XShortcut *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_LENGTH_R_DATA);
    return Data;
}

void XShortcut_InterruptGlobalEnable(XShortcut *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_GIE, 1);
}

void XShortcut_InterruptGlobalDisable(XShortcut *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_GIE, 0);
}

void XShortcut_InterruptEnable(XShortcut *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_IER);
    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_IER, Register | Mask);
}

void XShortcut_InterruptDisable(XShortcut *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_IER);
    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_IER, Register & (~Mask));
}

void XShortcut_InterruptClear(XShortcut *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XShortcut_WriteReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_ISR, Mask);
}

u32 XShortcut_InterruptGetEnabled(XShortcut *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_IER);
}

u32 XShortcut_InterruptGetStatus(XShortcut *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XShortcut_ReadReg(InstancePtr->Ctrl_BaseAddress, XSHORTCUT_CTRL_ADDR_ISR);
}

