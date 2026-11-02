// ==============================================================
// Vivado(TM) HLS - High-Level Synthesis from C, C++ and SystemC v2019.2 (64-bit)
// Copyright 1986-2019 Xilinx, Inc. All Rights Reserved.
// ==============================================================
/***************************** Include Files *********************************/
#include "xpwdwconv.h"

/************************** Function Implementation *************************/
int XPwdwconv_CfgInitialize(XPwdwconv *InstancePtr, XPwdwconv_Config *ConfigPtr) {
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

void XPwdwconv_Start(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_AP_CTRL) & 0x80;
    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XPwdwconv_IsDone(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XPwdwconv_IsIdle(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XPwdwconv_IsReady(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XPwdwconv_EnableAutoRestart(XPwdwconv *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_AP_CTRL, 0x80);
}

void XPwdwconv_DisableAutoRestart(XPwdwconv *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_AP_CTRL, 0);
}

void XPwdwconv_Set_PBUS1_V(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_PBUS1_V_DATA, Data);
}

u32 XPwdwconv_Get_PBUS1_V(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_PBUS1_V_DATA);
    return Data;
}

void XPwdwconv_Set_PBUS2_V(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_PBUS2_V_DATA, Data);
}

u32 XPwdwconv_Get_PBUS2_V(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_PBUS2_V_DATA);
    return Data;
}

void XPwdwconv_Set_PBUS3_V(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_PBUS3_V_DATA, Data);
}

u32 XPwdwconv_Get_PBUS3_V(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_PBUS3_V_DATA);
    return Data;
}

void XPwdwconv_Set_PBUS4_V(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_PBUS4_V_DATA, Data);
}

u32 XPwdwconv_Get_PBUS4_V(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_PBUS4_V_DATA);
    return Data;
}

void XPwdwconv_Set_SBUS1_V(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_SBUS1_V_DATA, Data);
}

u32 XPwdwconv_Get_SBUS1_V(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_SBUS1_V_DATA);
    return Data;
}

void XPwdwconv_Set_SBUS2_V(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_SBUS2_V_DATA, Data);
}

u32 XPwdwconv_Get_SBUS2_V(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_SBUS2_V_DATA);
    return Data;
}

void XPwdwconv_Set_ch_in(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_CH_IN_DATA, Data);
}

u32 XPwdwconv_Get_ch_in(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_CH_IN_DATA);
    return Data;
}

void XPwdwconv_Set_ch_out(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_CH_OUT_DATA, Data);
}

u32 XPwdwconv_Get_ch_out(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_CH_OUT_DATA);
    return Data;
}

void XPwdwconv_Set_stride(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_STRIDE_DATA, Data);
}

u32 XPwdwconv_Get_stride(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_STRIDE_DATA);
    return Data;
}

void XPwdwconv_Set_fsize(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_FSIZE_DATA, Data);
}

u32 XPwdwconv_Get_fsize(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_FSIZE_DATA);
    return Data;
}

void XPwdwconv_Set_act(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_ACT_DATA, Data);
}

u32 XPwdwconv_Get_act(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_ACT_DATA);
    return Data;
}

void XPwdwconv_Set_mode(XPwdwconv *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_MODE_DATA, Data);
}

u32 XPwdwconv_Get_mode(XPwdwconv *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_MODE_DATA);
    return Data;
}

void XPwdwconv_InterruptGlobalEnable(XPwdwconv *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_GIE, 1);
}

void XPwdwconv_InterruptGlobalDisable(XPwdwconv *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_GIE, 0);
}

void XPwdwconv_InterruptEnable(XPwdwconv *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_IER);
    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_IER, Register | Mask);
}

void XPwdwconv_InterruptDisable(XPwdwconv *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_IER);
    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_IER, Register & (~Mask));
}

void XPwdwconv_InterruptClear(XPwdwconv *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XPwdwconv_WriteReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_ISR, Mask);
}

u32 XPwdwconv_InterruptGetEnabled(XPwdwconv *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_IER);
}

u32 XPwdwconv_InterruptGetStatus(XPwdwconv *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XPwdwconv_ReadReg(InstancePtr->Ctrl_BaseAddress, XPWDWCONV_CTRL_ADDR_ISR);
}

