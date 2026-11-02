#ifndef __LCD_H
#define __LCD_H
#include "common.h"
#include "iic.h"


typedef struct { uint16_t x; uint16_t y; } TouchData;
extern TouchData touch_Data[5];
extern XAxiVdma LCD_Ptr;
extern XGpioPs Gpio;
extern uint32_t POINT_COLOR;
extern uint32_t BACK_COLOR;
extern uint8_t touch_start_flag;
extern uint8_t touch_one_flag;

#define LCD_W (800)
#define LCD_H (480)
/* 为1时，所有通过LCD_DrawPoint绘制的图片、文字和按钮绕整屏中心旋转180度。 */
#ifndef LCD_FLIP_DISPLAY
#define LCD_FLIP_DISPLAY (1)
#endif
#define Font_12 12
#define Font_16 16
#define Font_24 24
#define Font_32 32

#define BYTES_PIXEL 3
#define POINT_RED 0x00FF0000
#define POINT_GREEN 0x0000FF00
#define POINT_BLUE 0x000000FF
#define GPIO_BASEADDR HW_GPIO_BASEADDR
#define GPIO_INTERRUPT_ID HW_GPIO_INTR_ID
#define GPIO_BANK XGPIOPS_BANK0
#define GPIO_INT_PIN 0
#define GPIO_RST_PIN 54
#define SLAVE_DEV_ADDR 0x5D
#define GT_CTRL_REG 0X8040
#define GT_CFGS_REG 0X8047
#define GT_CHECK_REG 0X80FF
#define GT_PID_REG 0X8140
#define GT_GSTID_REG 0X814E
#define GT_TP1_REG 0X8150
#define GT_TP2_REG 0X8158
#define GT_TP3_REG 0X8160
#define GT_TP4_REG 0X8168
#define GT_TP5_REG 0X8170
#define GT911_WR_Reg(REG_ADDR, Data, len) PS_IIC_SeqWrite_Reg(&IicPs0,SLAVE_DEV_ADDR,REG16,REG_ADDR,Data,len)
#define GT911_RD_Reg(REG_ADDR, Data, len) PS_IIC_SeqRead_Reg(&IicPs0,SLAVE_DEV_ADDR,REG16,REG_ADDR,Data,len)


int LCD_Init(void);
void LCD_Refresh(void);
void LCD_Clear(uint32_t Color);
void LCD_DrawPoint(uint16_t X,uint16_t Y,uint32_t Color);
void LCD_ShowChar(char chr,uint16_t X,uint16_t Y,uint8_t Font,uint32_t POINT_COLOR);
/* 输入为交错BGR888。Scale=1原尺寸，Scale=2用LCD_DrawPoint填充2x2像素。Scale=0时不绘制，超出LCD的部分会裁剪；绘制后调用LCD_Refresh。 */
void LCD_ShowPicture(const uint8_t *image,uint16_t x,uint16_t y,
        uint16_t Wid,uint16_t High,uint8_t Scale);
uint32_t Gen_Color(uint32_t R,uint32_t G,uint32_t B);
int LCD_Touch_Init(void);
void Check_Touch(void);
void LCD_CleanArea(uint16_t x , uint16_t y , uint16_t x_size , uint16_t y_size ,uint32_t Color);
void LCD_Print(uint16_t x ,uint16_t y , uint8_t Font , uint32_t BackGround , uint32_t Color,char const* const _Format, ...);


#endif
