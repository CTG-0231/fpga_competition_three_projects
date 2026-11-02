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
// 0x10 : Data signal of PBUS1_V
//        bit 31~0 - PBUS1_V[31:0] (Read/Write)
// 0x14 : reserved
// 0x18 : Data signal of PBUS2_V
//        bit 31~0 - PBUS2_V[31:0] (Read/Write)
// 0x1c : reserved
// 0x20 : Data signal of PBUS3_V
//        bit 31~0 - PBUS3_V[31:0] (Read/Write)
// 0x24 : reserved
// 0x28 : Data signal of PBUS4_V
//        bit 31~0 - PBUS4_V[31:0] (Read/Write)
// 0x2c : reserved
// 0x30 : Data signal of SBUS1_V
//        bit 31~0 - SBUS1_V[31:0] (Read/Write)
// 0x34 : reserved
// 0x38 : Data signal of SBUS2_V
//        bit 31~0 - SBUS2_V[31:0] (Read/Write)
// 0x3c : reserved
// 0x40 : Data signal of ch_in
//        bit 31~0 - ch_in[31:0] (Read/Write)
// 0x44 : reserved
// 0x48 : Data signal of ch_out
//        bit 31~0 - ch_out[31:0] (Read/Write)
// 0x4c : reserved
// 0x50 : Data signal of stride
//        bit 31~0 - stride[31:0] (Read/Write)
// 0x54 : reserved
// 0x58 : Data signal of fsize
//        bit 31~0 - fsize[31:0] (Read/Write)
// 0x5c : reserved
// 0x60 : Data signal of act
//        bit 31~0 - act[31:0] (Read/Write)
// 0x64 : reserved
// 0x68 : Data signal of mode
//        bit 31~0 - mode[31:0] (Read/Write)
// 0x6c : reserved
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XPWDWCONV_CTRL_ADDR_AP_CTRL      0x00
#define XPWDWCONV_CTRL_ADDR_GIE          0x04
#define XPWDWCONV_CTRL_ADDR_IER          0x08
#define XPWDWCONV_CTRL_ADDR_ISR          0x0c
#define XPWDWCONV_CTRL_ADDR_PBUS1_V_DATA 0x10
#define XPWDWCONV_CTRL_BITS_PBUS1_V_DATA 32
#define XPWDWCONV_CTRL_ADDR_PBUS2_V_DATA 0x18
#define XPWDWCONV_CTRL_BITS_PBUS2_V_DATA 32
#define XPWDWCONV_CTRL_ADDR_PBUS3_V_DATA 0x20
#define XPWDWCONV_CTRL_BITS_PBUS3_V_DATA 32
#define XPWDWCONV_CTRL_ADDR_PBUS4_V_DATA 0x28
#define XPWDWCONV_CTRL_BITS_PBUS4_V_DATA 32
#define XPWDWCONV_CTRL_ADDR_SBUS1_V_DATA 0x30
#define XPWDWCONV_CTRL_BITS_SBUS1_V_DATA 32
#define XPWDWCONV_CTRL_ADDR_SBUS2_V_DATA 0x38
#define XPWDWCONV_CTRL_BITS_SBUS2_V_DATA 32
#define XPWDWCONV_CTRL_ADDR_CH_IN_DATA   0x40
#define XPWDWCONV_CTRL_BITS_CH_IN_DATA   32
#define XPWDWCONV_CTRL_ADDR_CH_OUT_DATA  0x48
#define XPWDWCONV_CTRL_BITS_CH_OUT_DATA  32
#define XPWDWCONV_CTRL_ADDR_STRIDE_DATA  0x50
#define XPWDWCONV_CTRL_BITS_STRIDE_DATA  32
#define XPWDWCONV_CTRL_ADDR_FSIZE_DATA   0x58
#define XPWDWCONV_CTRL_BITS_FSIZE_DATA   32
#define XPWDWCONV_CTRL_ADDR_ACT_DATA     0x60
#define XPWDWCONV_CTRL_BITS_ACT_DATA     32
#define XPWDWCONV_CTRL_ADDR_MODE_DATA    0x68
#define XPWDWCONV_CTRL_BITS_MODE_DATA    32

