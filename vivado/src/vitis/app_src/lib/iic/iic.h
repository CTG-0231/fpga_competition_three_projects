#ifndef __IIC_H
#define __IIC_H

/* PS IIC轮询传输、寄存器读写与中断接口。 */
#include "common.h"
#include "xiicps.h"
#include "scu.h"

extern XIicPs IicPs1;
extern XIicPs IicPs0;

#define	REG8		8
#define	REG16		16

/* SDT 配置使用基地址；异步上下文和中断接口供 IIC0 触摸屏使用。 */
int IIC_Init(XIicPs *IicPs, UINTPTR BaseAddress, u32 SclkHz);
int IIC_Itr_Init(XIicPs *IicPs, UINTPTR BaseAddress, u32 SclkHz);

int IIC_Write(XIicPs *IicPs, u16 SlaveAddr, const u8 *Data, u32 Length);
int IIC_Read(XIicPs *IicPs, u16 SlaveAddr, u8 *Data, u32 Length);

int IIC_WriteRead(XIicPs *IicPs, u16 SlaveAddr,
		const u8 *WriteData, u32 WriteLength,
		u8 *ReadData, u32 ReadLength);
uint8_t PS_IIC_Read_Reg(XIicPs *InstPtr,uint8_t SlaveID, uint8_t RegBIT, uint16_t reg);

int PS_IIC_SeqWrite_Reg(XIicPs *InstPtr,uint8_t SlaveID, uint8_t RegBIT,
		uint16_t reg, uint8_t *send_dat, uint32_t send_len);
int PS_IIC_SeqRead_Reg(XIicPs *InstPtr,uint8_t SlaveID, uint8_t RegBIT,
		uint16_t reg,uint8_t *recv_data, uint32_t recv_len);

uint8_t IIC_Itr_WaitForCompletion();


#endif
