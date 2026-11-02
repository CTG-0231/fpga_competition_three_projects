#include "iic.h"
#include "hw_config.h"

/* IIC驱动封装，使用Xilinx XIicPs主机模式接口。 */
#define IIC_BUS_IDLE_TIMEOUT 1000000U

/* 分别供触摸屏和摄像头使用的IIC控制器实例。 */
XIicPs IicPs0;
XIicPs IicPs1;

typedef enum {
    IIC_ASYNC_IDLE = 0,
    IIC_ASYNC_SEND,
    IIC_ASYNC_NEED_RECV,
    IIC_ASYNC_RECV,
    IIC_ASYNC_DONE,
    IIC_ASYNC_ERROR
} IIC_ASYNC_STATE;

typedef struct {
    XIicPs *Iic;
    u8 SlaveAddr;

    u8 TxBuf[256];
    u32 TxLen;

    u8 *RxBuf;
    u32 RxLen;

    u8 Operation;       // 0: read, 1: write
    volatile IIC_ASYNC_STATE State;
} IIC_ASYNC_CTX;

IIC_ASYNC_CTX IIC0;

/* 等待总线空闲；超时后清理FIFO和HOLD状态，供后续传输重试。 */
static int IIC_WaitBusIdle(XIicPs *IicPs)
{
	u32 Timeout;

	if ((IicPs == NULL) || (IicPs->IsReady != XIL_COMPONENT_IS_READY)) {
		return XST_FAILURE;
	}

	for (Timeout = 0U; Timeout < IIC_BUS_IDLE_TIMEOUT; ++Timeout) {
		if (XIicPs_BusIsBusy(IicPs) == 0) {
			return XST_SUCCESS;
		}
	}

	/* 返回总线忙错误之前，清理残留的HOLD和FIFO状态。 */
	XIicPs_Abort(IicPs);
	return XST_IIC_BUS_BUSY;
}

int IIC_Init(XIicPs *IicPs, UINTPTR BaseAddress, u32 SclkHz)
{
	XIicPs_Config *Config;
	int Status;

	if (IicPs == NULL) {
		return XST_INVALID_PARAM;
	}

	Config = XIicPs_LookupConfig(BaseAddress);
	if (Config == NULL) {
		return XST_DEVICE_NOT_FOUND;
	}

	Status = XIicPs_CfgInitialize(IicPs, Config, Config->BaseAddress);
	if (Status != XST_SUCCESS) {
		return Status;
	}

	/* 执行控制器自检，确认PS IIC外设可用。 */
	Status = XIicPs_SelfTest(IicPs);
	if (Status != XST_SUCCESS) {
		return Status;
	}

	/* 设置IIC时钟频率，单位为赫兹。 */
	Status = XIicPs_SetSClk(IicPs, SclkHz);
	if (Status != XST_SUCCESS) {
		return Status;
	}

	/* 使用七位从机地址。 */
	return XIicPs_SetOptions(IicPs, XIICPS_7_BIT_ADDR_OPTION);
}

void IIC_Handler(void *CallbackRef, u32 Event)
{
	IIC_ASYNC_CTX *Ctx = (IIC_ASYNC_CTX *)CallbackRef;

	 if (Event & (XIICPS_EVENT_NACK |
                 XIICPS_EVENT_ARB_LOST |
                 XIICPS_EVENT_TIME_OUT |
                 XIICPS_EVENT_RX_OVR |
                 XIICPS_EVENT_TX_OVR)) {
        Ctx->State = IIC_ASYNC_ERROR;
        return;
    }
	else if (Event & XIICPS_EVENT_COMPLETE_SEND) {
		if (Ctx->Operation == 0) {
			Ctx->State = IIC_ASYNC_NEED_RECV;
		} else {
			Ctx->State = IIC_ASYNC_DONE;
		}
	}
	else if (Event & XIICPS_EVENT_COMPLETE_RECV) {
		Ctx->State = IIC_ASYNC_DONE;
	}
	
}


int IIC_Itr_Init(XIicPs *IicPs, UINTPTR BaseAddress, u32 SclkHz)
{
	int Status;

	if ((IicPs == NULL) || (BaseAddress != HW_IIC0_BASEADDR)) {
		return XST_INVALID_PARAM;
	}
	if (Intc.IsReady != XIL_COMPONENT_IS_READY) {
		return XST_FAILURE;
	}
	/* main 已先初始化 IIC0；独立调用时也须先建立 SDT 驱动配置。 */
	if (IicPs->IsReady != XIL_COMPONENT_IS_READY) {
		Status = IIC_Init(IicPs, BaseAddress, SclkHz);
		if (Status != XST_SUCCESS) {
			return Status;
		}
	} else if (IicPs->Config.BaseAddress != BaseAddress) {
		return XST_INVALID_PARAM;
	}

	IIC0.Iic = IicPs;
	IIC0.State = IIC_ASYNC_IDLE;

	/* HW_IIC0_INTR_ID 已由 SDT 编码转换为 GIC 原始 IRQ 编号。 */
	Status = XScuGic_Connect(&Intc, HW_IIC0_INTR_ID,
			(Xil_InterruptHandler)XIicPs_MasterInterruptHandler,
			(void *)IicPs);
	if (Status != XST_SUCCESS) {
		return Status;
	}

	XIicPs_SetStatusHandler(IicPs, (void *)&IIC0, IIC_Handler);
	XScuGic_Enable(&Intc, HW_IIC0_INTR_ID);
	
	return XST_SUCCESS;
}


/* 向从机写入数据；SlaveAddr使用七位地址，例如OV5640为0x3C，不要左移。 */
int IIC_Write(XIicPs *IicPs, u16 SlaveAddr, const u8 *Data, u32 Length)
{
	int Status;

	if ((IicPs == NULL) || (IicPs->IsReady != XIL_COMPONENT_IS_READY) ||
			(Data == NULL) || (Length == 0U)) {
		return XST_INVALID_PARAM;
	}

	Status = IIC_WaitBusIdle(IicPs);
	if (Status != XST_SUCCESS) {
		return Status;
	}

	/* 以轮询方式等待本次发送完成。 */
	Status = XIicPs_MasterSendPolled(IicPs, (u8 *)Data, (s32)Length,
			SlaveAddr);
	if (Status != XST_SUCCESS) {
		XIicPs_Abort(IicPs);
		return Status;
	}

	return IIC_WaitBusIdle(IicPs);
}

int IIC_Read(XIicPs *IicPs, u16 SlaveAddr, u8 *Data, u32 Length)
{
	int Status;

	if ((IicPs == NULL) || (IicPs->IsReady != XIL_COMPONENT_IS_READY) ||
			(Data == NULL) || (Length == 0U)) {
		return XST_INVALID_PARAM;
	}

	Status = IIC_WaitBusIdle(IicPs);
	if (Status != XST_SUCCESS) {
		return Status;
	}

	/* 接收时同样使用七位从机地址。 */
	Status = XIicPs_MasterRecvPolled(IicPs, Data, (s32)Length, SlaveAddr);
	if (Status != XST_SUCCESS) {
		XIicPs_Abort(IicPs);
		return Status;
	}

	return IIC_WaitBusIdle(IicPs);
}






/* 连续写入从机寄存器。InstPtr为控制器实例，SlaveID为七位地址，
 * RegBIT选择八位或十六位寄存器地址，reg为起始寄存器，
 * send_dat为数据缓冲区，send_len为写入字节数。 */
int PS_IIC_SeqWrite_Reg(XIicPs *InstPtr,uint8_t SlaveID, uint8_t RegBIT,
		uint16_t reg, uint8_t *send_dat, uint32_t send_len)
{
	uint8_t WR_Buffer[send_len+2];
	int Status;

	if ((InstPtr == NULL) || (send_dat == NULL) || (send_len == 0U)) {
		return XST_INVALID_PARAM;
	}

	if(RegBIT == REG8)
	{
		WR_Buffer[0] = reg;
		memcpy(WR_Buffer+1,send_dat,send_len);

		// 发送寄存器地址和数据
		Status = IIC_Write(InstPtr,SlaveID ,WR_Buffer,send_len+1 );
		return Status;
	}
	else if(RegBIT == REG16)
	{
		WR_Buffer[0] = reg>>8;		// 寄存器地址高八位
		WR_Buffer[1] = reg&0x00FF;	// 寄存器地址低八位
		memcpy(WR_Buffer+2,send_dat,send_len);
		// 发送寄存器地址和数据
		Status = IIC_Write(InstPtr,SlaveID,  WR_Buffer,send_len+2);
		return Status;
	}

	return XST_INVALID_PARAM;
}
/* 连续读取从机寄存器。InstPtr为控制器实例，SlaveID为七位地址，
 * RegBIT选择八位或十六位寄存器地址，reg为起始寄存器，
 * recv_data接收读取结果，recv_len为读取字节数。 */
int PS_IIC_SeqRead_Reg(XIicPs *InstPtr,uint8_t SlaveID, uint8_t RegBIT,
		uint16_t reg,uint8_t *recv_data, uint32_t recv_len)
{
	uint8_t WR_Buffer[2];
	int Status;

	if ((InstPtr == NULL) || (recv_data == NULL) || (recv_len == 0U)) {
		return XST_INVALID_PARAM;
	}

	if(RegBIT == REG8)
	{
		WR_Buffer[0] = reg;

		// 发送要读取的寄存器地址
		Status = IIC_Write(InstPtr,SlaveID, WR_Buffer,1 );
	}
	else if(RegBIT == REG16)
	{
		WR_Buffer[0] = reg>>8;		// 寄存器地址高八位
		WR_Buffer[1] = reg&0x00FF;	// 寄存器地址低八位
		// 发送要读取的寄存器地址
		Status = IIC_Write(InstPtr, SlaveID ,WR_Buffer,2);
	}
	else
	{
		return XST_INVALID_PARAM;
	}

	if (Status != XST_SUCCESS) {
		return Status;
	}

	return IIC_Read(InstPtr,SlaveID,recv_data,recv_len);

}


void IIC_Itr_SeqWrite_Reg(uint8_t SlaveID, uint8_t RegBIT, uint16_t reg, uint8_t *send_dat, uint32_t send_len)
{
	switch(IIC0.State) {
		case IIC_ASYNC_IDLE:
			IIC0.SlaveAddr = SlaveID;
			IIC0.TxLen = send_len;
			IIC0.RxLen = 0;
			IIC0.Operation = 1; // write
			if(RegBIT == REG8) {
				IIC0.TxBuf[0] = reg;
				memcpy(IIC0.TxBuf+1, send_dat, send_len);
				IIC0.TxLen += 1;
			} else if(RegBIT == REG16) {
				IIC0.TxBuf[0] = reg >> 8;
				IIC0.TxBuf[1] = reg & 0x00FF;
				memcpy(IIC0.TxBuf+2, send_dat, send_len);
				IIC0.TxLen += 2;
			}
			IIC0.State = IIC_ASYNC_SEND;
			XIicPs_MasterSend(IIC0.Iic, IIC0.TxBuf, IIC0.TxLen, IIC0.SlaveAddr);
			break;

		case IIC_ASYNC_SEND:
		case IIC_ASYNC_NEED_RECV:
		case IIC_ASYNC_RECV:
		case IIC_ASYNC_DONE:
		case IIC_ASYNC_ERROR:
			// Handle other states if necessary
			break;

		default:
			break;
	}
}

void IIC_Itr_SeqRead_Reg(uint8_t SlaveID, uint8_t RegBIT, uint16_t reg, uint8_t *recv_data, uint32_t recv_len)
{
	switch(IIC0.State) {
		case IIC_ASYNC_IDLE:
			IIC0.SlaveAddr = SlaveID;
			IIC0.TxLen = 0;
			IIC0.RxLen = recv_len;
			IIC0.RxBuf = recv_data;
			IIC0.Operation = 0; // read
			if(RegBIT == REG8) {
				IIC0.TxBuf[0] = reg;
				IIC0.TxLen += 1;
			} else if(RegBIT == REG16) {
				IIC0.TxBuf[0] = reg >> 8;
				IIC0.TxBuf[1] = reg & 0x00FF;
				IIC0.TxLen += 2;
			}
			IIC0.State = IIC_ASYNC_SEND; // After sending the register address, we will need to receive data
			XIicPs_MasterSend(IIC0.Iic, IIC0.TxBuf, IIC0.TxLen, IIC0.SlaveAddr);
			
			break;

		case IIC_ASYNC_SEND:
		case IIC_ASYNC_NEED_RECV:
		case IIC_ASYNC_RECV:
		case IIC_ASYNC_DONE:
		case IIC_ASYNC_ERROR:
			// Handle other states if necessary
			break;

		default:
			break;
	}
}

uint8_t IIC_Itr_WaitForCompletion()
{
	switch(IIC0.State) {
		case IIC_ASYNC_NEED_RECV:
			IIC0.State = IIC_ASYNC_RECV;
			IIC0.Operation = 1; // read
			XIicPs_MasterRecv(IIC0.Iic, IIC0.RxBuf, IIC0.RxLen, IIC0.SlaveAddr);
			return XST_DEVICE_BUSY;
			break;
		case IIC_ASYNC_ERROR:
			// Handle error
			IIC0.State = IIC_ASYNC_IDLE;
			XIicPs_Abort(IIC0.Iic);
			return XST_FAILURE; // Indicate error
			break;
		case IIC_ASYNC_DONE:
			if(IIC0.Operation == 1) {
				IIC0.State = IIC_ASYNC_IDLE;
				return XST_SUCCESS;
			}
			return XST_DEVICE_BUSY;
		case IIC_ASYNC_IDLE:
			return XST_SUCCESS; // Already idle, no operation in progress
			break;
		default:
			return XST_DEVICE_BUSY; // Still in progress
			// Still in progress, wait or handle accordingly
			break;
	}
}
