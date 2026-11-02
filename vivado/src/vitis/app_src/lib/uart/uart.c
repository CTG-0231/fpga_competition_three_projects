#include "uart.h"
#include <stdarg.h>


XUartPs UartPs1;
XScuGic UartIntc;
uint32_t UART1_ErrorCount;

static int UART_Configure(XUartPs *UartPs, UINTPTR BaseAddress, u32 Speed)
{
	XUartPs_Config *Config;
	int Status;

	if (UartPs == NULL) {
		return XST_INVALID_PARAM;
	}

	Config = XUartPs_LookupConfig(BaseAddress);
	if (Config == NULL) {
		return XST_DEVICE_NOT_FOUND;
	}

	Status = XUartPs_CfgInitialize(UartPs, Config, Config->BaseAddress);
	if (Status != XST_SUCCESS) {
		return Status;
	}

	Status = XUartPs_SetBaudRate(UartPs, Speed);
	return Status;
}

void UART_Init(XUartPs *UartPs, UINTPTR BaseAddress, uint32_t Speed){
	(void)UART_Configure(UartPs, BaseAddress, Speed);
}


void UART_Intr_Handler(void *CallBackRef, u32 Event, u32 EventData);
int UART_Intr_Init(XUartPs *UartPs, XScuGic *IntcInstancePtr,
		UINTPTR BaseAddress, u32 Speed, u32 UartIntrId)
{
	int Status;
	u32 IntrMask;

	if ((UartPs == NULL) || (IntcInstancePtr == NULL)) {
		return XST_INVALID_PARAM;
	}
	if (IntcInstancePtr->IsReady != XIL_COMPONENT_IS_READY) {
		return XST_FAILURE;
	}

	Status = UART_Configure(UartPs, BaseAddress, Speed);
	if (Status != XST_SUCCESS) {
		return Status;
	}


	Status = XUartPs_SelfTest(UartPs);
	if (Status != XST_SUCCESS) {
		return Status;
	}


	Status = XScuGic_Connect(IntcInstancePtr, UartIntrId,
			(Xil_InterruptHandler)XUartPs_InterruptHandler, UartPs);
	if (Status != XST_SUCCESS) {
		return Status;
	}


	XScuGic_Enable(IntcInstancePtr, UartIntrId);
	XUartPs_SetHandler(UartPs, (XUartPs_Handler)UART_Intr_Handler, UartPs);

	IntrMask = XUARTPS_IXR_TOUT | XUARTPS_IXR_PARITY |
			XUARTPS_IXR_FRAMING | XUARTPS_IXR_OVER |
			XUARTPS_IXR_RXFULL | XUARTPS_IXR_RXOVR;
	XUartPs_SetInterruptMask(UartPs, IntrMask);
	XUartPs_SetRecvTimeout(UartPs, 8U);
	XUartPs_SetOperMode(UartPs, XUARTPS_OPER_MODE_NORMAL);

	return XST_SUCCESS;

}

void UART_Print(char const* const _Format, ...){
	char str[256];
	va_list args;
	int Length;
	unsigned int i;
	if ((_Format == NULL) ||
			(UartPs1.IsReady != XIL_COMPONENT_IS_READY)) {
		return;
	}
	va_start(args, _Format);
	Length = vsnprintf(str, sizeof(str), _Format, args);
	va_end(args);
	if (Length <= 0) {
		return;
	}
	if ((unsigned int)Length >= sizeof(str)) {
		Length = sizeof(str) - 1U;
	}

	/* 同步写入发送FIFO，防止函数返回后中断继续读取已经失效的栈缓冲区。 */
	for (i = 0U; i < (unsigned int)Length; ++i) {
		XUartPs_SendByte(UartPs1.Config.BaseAddress, (u8)str[i]);
	}

}

void UART_Intr_Handler(void *CallBackRef, u32 Event, u32 EventData)
{
	XUartPs *UartPs = (XUartPs *)CallBackRef;
	if (UartPs == NULL) {
		return;
	}
	if(CallBackRef != &UartPs1){
		if (Event & XUARTPS_IXR_RXOVR) {
			UART1_ErrorCount++;
		}
		if (Event & XUARTPS_IXR_RXFULL) {
			UART1_ErrorCount++;
		}
		if (Event & XUARTPS_IXR_TOUT) {
			UART1_ErrorCount++;
		}
		if (Event & XUARTPS_IXR_PARITY) {
			UART1_ErrorCount++;
		}
		if (Event & XUARTPS_IXR_FRAMING) {
			UART1_ErrorCount++;
		}
	}

}

