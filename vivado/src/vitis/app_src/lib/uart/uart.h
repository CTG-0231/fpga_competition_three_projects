#ifndef __UART_H
#define __UART_H

/* UART 驱动接口：普通轮询发送、格式化打印和中断初始化。 */
#include "common.h"
#include "stdio.h"
extern XUartPs UartPs1;
extern XScuGic UartIntc;

/* Vitis SDT 使用外设基地址查找配置；中断参数为 GIC 的原始 IRQ 编号。 */
/* 底层发送和接收接口：
 * XUartPs_Send(XUartPs *InstancePtr, u8 *BufferPtr, u32 NumBytes)
 * XUartPs_Recv(XUartPs *InstancePtr, u8 *BufferPtr, u32 NumBytes)
 */


/* 初始化 UART，Speed 为波特率，例如 115200。 */
void UART_Init(XUartPs *UartPs, UINTPTR BaseAddress, uint32_t Speed);

/*
 * 连接 UART 中断。IntcInstancePtr 须先由 SCU_Init 初始化。
 * Handler 的原型为：
 * void Handler(void *Ref, u32 Event, unsigned int EventData);
 */
int UART_Intr_Init(XUartPs *UartPs, XScuGic *IntcInstancePtr,
		UINTPTR BaseAddress, u32 Speed, u32 UartIntrId);

/* 使用全局 UartPs1 发送格式化字符串。 */
void UART_Print(char const* const _Format, ...);

#endif
