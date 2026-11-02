// ==============================================================
// Vivado(TM) HLS - High-Level Synthesis from C, C++ and SystemC v2019.2 (64-bit)
// Copyright 1986-2019 Xilinx, Inc. All Rights Reserved.
// ==============================================================
// CTRL
// 0x00 : Control signals
//        bit 0  - ap_start (Read/Write/COH)
//        bit 1  - ap_done (Read/COR)
//        bit 2  - ap_idle (Read)
//        bit 3  - ap_ready (Read)
//        bit 7  - auto_restart (Read/Write)
//        others - reserved
// 0x04 : Global Interrupt Enable Register
//        bit 0  - Global Interrupt Enable (Read/Write)
//        others - reserved
// 0x08 : IP Interrupt Enable Register (Read/Write)
//        bit 0  - Channel 0 (ap_done)
//        bit 1  - Channel 1 (ap_ready)
//        others - reserved
// 0x0c : IP Interrupt Status Register (Read/TOW)
//        bit 0  - Channel 0 (ap_done)
//        bit 1  - Channel 1 (ap_ready)
//        others - reserved
// 0x10 : Data signal of src1_V
//        bit 31~0 - src1_V[31:0] (Read/Write)
// 0x14 : reserved
// 0x18 : Data signal of src2_V
//        bit 31~0 - src2_V[31:0] (Read/Write)
// 0x1c : reserved
// 0x20 : Data signal of dest_V
//        bit 31~0 - dest_V[31:0] (Read/Write)
// 0x24 : reserved
// 0x28 : Data signal of length_r
//        bit 31~0 - length_r[31:0] (Read/Write)
// 0x2c : reserved
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XSHORTCUT_CTRL_ADDR_AP_CTRL       0x00
#define XSHORTCUT_CTRL_ADDR_GIE           0x04
#define XSHORTCUT_CTRL_ADDR_IER           0x08
#define XSHORTCUT_CTRL_ADDR_ISR           0x0c
#define XSHORTCUT_CTRL_ADDR_SRC1_V_DATA   0x10
#define XSHORTCUT_CTRL_BITS_SRC1_V_DATA   32
#define XSHORTCUT_CTRL_ADDR_SRC2_V_DATA   0x18
#define XSHORTCUT_CTRL_BITS_SRC2_V_DATA   32
#define XSHORTCUT_CTRL_ADDR_DEST_V_DATA   0x20
#define XSHORTCUT_CTRL_BITS_DEST_V_DATA   32
#define XSHORTCUT_CTRL_ADDR_LENGTH_R_DATA 0x28
#define XSHORTCUT_CTRL_BITS_LENGTH_R_DATA 32

