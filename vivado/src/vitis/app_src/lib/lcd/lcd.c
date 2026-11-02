#include "lcd.h"
#include "font.h"
#include "xil_printf.h"
#include "scu.h"
#include "uart.h"
XAxiVdma LCD_Ptr;
XVtc LCD_Vtc;
XGpioPs Gpio;

uint8_t touch_start_flag=0;
uint8_t touch_one_flag=0;
uint8_t *Buffptr = (uint8_t*)(HW_LCD_BUFFER_ADDR);

uint32_t srcBuff=(HW_LCD_BUFFER_ADDR);
uint32_t  POINT_COLOR;// 当前画笔颜色
uint32_t  BACK_COLOR; // 当前背景颜色


TouchData touch_Data[5];

void IIC_Itr_SeqWrite_Reg(uint8_t SlaveID, uint8_t RegBIT, uint16_t reg, uint8_t *send_dat, uint32_t send_len);
void IIC_Itr_SeqRead_Reg(uint8_t SlaveID, uint8_t RegBIT, uint16_t reg, uint8_t *recv_data, uint32_t recv_len);
uint8_t IIC_Itr_WaitForCompletion();


#define GT911_WR_Reg_Itr(REG_ADDR, Data, len)  IIC_Itr_SeqWrite_Reg(SLAVE_DEV_ADDR, REG16, REG_ADDR, Data,len)
#define GT911_RD_Reg_Itr(REG_ADDR, Data, len)  IIC_Itr_SeqRead_Reg(SLAVE_DEV_ADDR, REG16, REG_ADDR, Data,len)

volatile u8 ToughFlag = 0;

const u8 GT911_CFG_TBL[]= {
		'D',0x20,0x3 ,0xe0,0x1 ,0xa ,0xd ,0x0 ,0x1 ,0xa ,
		0x28,0xf ,0x50,0x32,0x3 ,0xF ,0x5F ,0x5F ,0x0 ,0x0 ,
		0x22,0x22,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x89,0x29,0xb ,
		0x26,0x24,0xea,0x4 ,0x0 ,0x0 ,0x0 ,0x2 ,0x3 ,0x1c,
		0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x3 ,0x64,0x32,0x0 ,0x0 ,
		0x0 ,0x14,0x37,0x94,0xc5,0x2 ,0x7 ,0x0 ,0x0 ,0x4 ,
		0xe8,0x13,0x0 ,0x97,0x1e,0x0 ,0x61,0x30,0x0 ,0x3e,
		0x4c,0x0 ,0x28,0x78,0x0 ,0x28,0x0 ,0x0 ,0x0 ,0x0 ,
		0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,
		0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,
		0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,
		0x0 ,0x0 ,0x16,0x14,0x12,0x10,0xe ,0xc ,0xa ,0x8 ,
		0x6 ,0x4 ,0x2 ,0xff,0xff,0xff,0xff,0xff,0xff,0xff,
		0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,
		0xff,0xff,0x22,0x21,0x20,0x1f,0x1e,0x1d,0x1c,0x18,
		0x16,0x12,0x10,0xf ,0xa ,0x8 ,0x6 ,0x4 ,0x2 ,0x0 ,
		0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,
		0xff,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,0x0 ,
		0x0 ,0x0 ,0x0 ,0x0 ,
};


int run_triple_frame_buffer(XAxiVdma* InstancePtr, int DeviceId, int hsize,
                int vsize, int buf_base_addr, int number_frame_count,
                int enable_frm_cnt_intr);
uint32_t Gen_Color(uint32_t R , uint32_t G ,uint32_t B){
	return 0x00000000|(R<<16)|(G<<8)|B;
}


int Vtc_Init(XVtc *Vtc_Inst)
{
        XVtc_Config *vtcConfig;
        vtcConfig = XVtc_LookupConfig(HW_VTC_BASEADDR);
        if (vtcConfig == NULL) return XST_DEVICE_NOT_FOUND;
        return XVtc_CfgInitialize(Vtc_Inst, vtcConfig, vtcConfig->BaseAddress);
}

int LCD_Init(void){
	int Status;

	Status = Vtc_Init(&LCD_Vtc);
    if (Status != XST_SUCCESS) return Status;
	memset((uint8_t*)srcBuff,0x00,LCD_W*LCD_H*BYTES_PIXEL);
	Status = run_triple_frame_buffer(&LCD_Ptr, 0, LCD_W, LCD_H,srcBuff, 0, 0);
	if (Status != XST_SUCCESS) {
		xil_printf("LCD VDMA init failed: %d\r\n", Status);
		return Status;
	}
	XVtc_EnableGenerator(&LCD_Vtc);
	return XST_SUCCESS;
}

void LCD_Refresh(){
	Xil_DCacheFlushRange((INTPTR)Buffptr,LCD_W * LCD_H * BYTES_PIXEL);
}

void LCD_Clear(uint32_t Color){
	for(uint16_t i=0;i<LCD_H;i++){
		for(uint16_t j=0;j<LCD_W;j++){
			Buffptr[(i*LCD_W+j)*BYTES_PIXEL]=Color&0x000000FF;
			Buffptr[(i*LCD_W+j)*BYTES_PIXEL+1]=(Color&0x0000FF00)>>8;
			Buffptr[(i*LCD_W+j)*BYTES_PIXEL+2]=(Color&0x00FF0000)>>16;
		}
	}
}




void LCD_DrawPoint(uint16_t X , uint16_t Y, uint32_t Color){
	if (X >= LCD_W || Y >= LCD_H) return;
#if LCD_FLIP_DISPLAY
	/* 图片、文字和按钮共用此入口，在这里执行整屏中心对称。 */
	X = LCD_W - 1U - X;
	Y = LCD_H - 1U - Y;
#endif
	Buffptr[(Y*LCD_W+X)*BYTES_PIXEL]=Color&0x000000FF;
	Buffptr[(Y*LCD_W+X)*BYTES_PIXEL+1]=(Color&0x0000FF00)>>8;
	Buffptr[(Y*LCD_W+X)*BYTES_PIXEL+2]=(Color&0x00FF0000)>>16;
} 

void LCD_CleanArea(uint16_t x , uint16_t y , uint16_t x_size , uint16_t y_size ,uint32_t Color){
	for (uint16_t i = x ; i< x + x_size ; i++){
		for (uint16_t j = y ; j< y + y_size ; j++){
			LCD_DrawPoint(i,j,Color);
		}
	}
	
}


void LCD_ShowChar(char chr , uint16_t X , uint16_t Y , uint8_t Font , uint32_t POINT_COLOR){
	uint16_t y0=Y;
	uint16_t x0=X;

	const uint8_t *temp;
	switch(Font){
		case 12:temp=asc2_1206[chr-32];break;
		case 16:temp=asc2_1608[chr-32];break;
		case 24:temp=asc2_2412[chr-32];break;
		case 32:temp=asc2_3216[chr-32];break;
		default:temp=asc2_1206[chr-32];break;
	}
    
	for(uint8_t i=0;i<Font/2;i++){
		const uint8_t *temp1=&temp[i*(Font/8+(Font%8?1:0))];
		if (x0+i>=LCD_W) return;
		for(uint8_t j=0;j<(Font/8+(Font%8?1:0));j++){
			for(uint8_t k=0;k<8;k++){
				if (y0+j*8+k>=LCD_H) return;
				if(*temp1&(0x80>>k)) LCD_DrawPoint(x0+i,y0+j*8+k,POINT_COLOR);
				if(j*8+k>=Font-1) break;
			}
			temp1++;
		}
	}
}

void LCD_Print(uint16_t x ,uint16_t y , uint8_t Font , uint32_t BackGround , uint32_t Color,char const* const _Format, ...){
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

	uint16_t x0=x;
	uint16_t y0=y;




	for (i = 0U; i < (unsigned int)Length; ++i) {
		if(str[i]>= ' ' && str[i]<='~') {

			LCD_CleanArea(x0 , y0 , Font/2 , Font ,BackGround);

			LCD_ShowChar(str[i],x0,y0,Font,Color);
			x0+=Font/2;
		}
		else if (str[i] == '\n'){
			y0+=Font;
			x0=x;
		}

	}
}

void LCD_ShowPicture(const uint8_t *image, uint16_t x, uint16_t y,
        uint16_t Wid, uint16_t High, uint8_t Scale)
{
    unsigned int row, col, dx, dy;
    if (image == NULL || Wid == 0U || High == 0U || Scale == 0U ||
            x >= LCD_W || y >= LCD_H) {
        return;
    }
    for (row = 0U; row < High; ++row) {
        unsigned int dest_y = y + row * Scale;
        if (dest_y >= LCD_H) break;
        for (col = 0U; col < Wid; ++col) {
            unsigned int dest_x = x + col * Scale;
            const uint8_t *pixel;
            uint32_t color;
            if (dest_x >= LCD_W) break;
            pixel = image + (row * Wid + col) * BYTES_PIXEL;
            color = (uint32_t)pixel[0] | ((uint32_t)pixel[1] << 8) |
                    ((uint32_t)pixel[2] << 16);
            /* 放大时相对坐标乘以Scale，并填满Scale乘Scale大小的像素块。 */
            for (dy = 0U; dy < Scale && dest_y + dy < LCD_H; ++dy) {
                for (dx = 0U; dx < Scale && dest_x + dx < LCD_W; ++dx) {
                    unsigned int draw_x = dest_x + dx;
                    unsigned int draw_y = dest_y + dy;
                    LCD_DrawPoint((uint16_t)draw_x,
                            (uint16_t)draw_y, color);
                }
            }
        }
    }
}

static void IntrHandler(void *CallBackRef, u32 Bank, u32 Status)
{
	XGpioPs *Gpio_Callback = (XGpioPs *)CallBackRef;
	u32 DataRead;

	
	DataRead = XGpioPs_ReadPin(Gpio_Callback, GPIO_INT_PIN);
	if (DataRead==0) {
		ToughFlag=1;
	}
}

u8 GT911_Send_Cfg(u8 mode)
{
    u8 buf[2];
    u8 i=0;
    buf[0]=0;
    buf[1]=mode;    // 是否掉电保存配置
    for(i=0; i<sizeof(GT911_CFG_TBL); i++)
        buf[0]+=GT911_CFG_TBL[i]; // 累加配置字节以计算校验和
    buf[0]=(~buf[0])+1;
    GT911_WR_Reg(GT_CFGS_REG,(u8*)GT911_CFG_TBL,sizeof(GT911_CFG_TBL));// 写入寄存器配置
    GT911_WR_Reg(GT_CHECK_REG,buf,2);// 写入校验和及配置更新标记
    return 0;
}

int LCD_Touch_Init(void){

	u8 id[5] = {0};
    u8 buff[1];
	XGpioPs_Config *ConfigPtr;
	ConfigPtr = XGpioPs_LookupConfig(HW_GPIO_BASEADDR);
    if (ConfigPtr == NULL) return XST_DEVICE_NOT_FOUND;
    int InitStatus = XGpioPs_CfgInitialize(&Gpio, ConfigPtr, ConfigPtr->BaseAddr);
    if (InitStatus != XST_SUCCESS) return InitStatus;
	// 初始化GT911复位和中断引脚
	

	XGpioPs_SetDirectionPin(&Gpio, GPIO_RST_PIN, 1);
	XGpioPs_SetDirectionPin(&Gpio, GPIO_INT_PIN, 1);

	XGpioPs_WritePin(&Gpio, GPIO_INT_PIN, 1);
	XGpioPs_WritePin(&Gpio, GPIO_RST_PIN, 0);
	usleep(10000);	
	XGpioPs_WritePin(&Gpio, GPIO_RST_PIN, 1);
	usleep(10000);
	XGpioPs_WritePin(&Gpio, GPIO_INT_PIN, 0);
	usleep(100000);
	GT911_RD_Reg(GT_PID_REG,id,4);
	UART_Print("ID:%s\n",id);
	buff[0]=0X02;
	GT911_WR_Reg(GT_CTRL_REG,buff,1);	// 软复位GT911
	GT911_RD_Reg(GT_CFGS_REG,buff,1);
	UART_Print("Previous version: %c\n",buff[0]);
		GT911_Send_Cfg(1);		// 更新配置并保存
	GT911_RD_Reg(GT_CFGS_REG,buff,1);		// 读取配置版本寄存器
	UART_Print("Current version: %c\n",buff[0]);		// 打印当前配置版本
	usleep(10000);		// 延时十毫秒
	buff[0]=0X00;
	GT911_WR_Reg(GT_CTRL_REG,buff,1);// 结束复位

	uint8_t buff_T[2];
	GT911_RD_Reg(0x8057,buff_T,2);
	UART_Print("x: %d y: %d\n",buff_T[0],buff_T[1]);
	// 初始化触摸中断
	XGpioPs_SetDirectionPin(&Gpio, GPIO_INT_PIN, 0);
	InitStatus = XScuGic_Connect(&Intc, GPIO_INTERRUPT_ID,
				(Xil_ExceptionHandler)XGpioPs_IntrHandler,
				(void *)(&Gpio));
    if (InitStatus != XST_SUCCESS) return InitStatus;
	XGpioPs_SetIntrType(&Gpio, GPIO_BANK, 0xFFFFFFFF , 0x00, 0x00);
	XGpioPs_SetCallbackHandler(&Gpio, (void *)(&Gpio), IntrHandler);
	XGpioPs_IntrEnable(&Gpio, GPIO_BANK, (1 << (GPIO_INT_PIN-GPIO_BANK*32)));
	XScuGic_Enable(&Intc, GPIO_INTERRUPT_ID);
    return XST_SUCCESS;
}

void Check_Touch(){
	
	static uint8_t Touch=0;// 缓存触摸状态寄存器
	static uint8_t TouchData[40];
	static uint8_t CleanData[1]={0};
	static uint8_t count=0;
	static uint8_t count_pre=0;
	if (ToughFlag>0) {
		GT911_RD_Reg(0x814E,&Touch,1);	// 读取触摸状态

		if((Touch>>7)&0x01){	// 检查触摸数据是否就绪
			count = Touch & 0x0F; // 获取触摸点数量
			/* 松手事件不沿用上次坐标，异常点数不得越过缓冲区。 */
			if (count > 5U) count = 0U;

			if (count > 0) {
				GT911_RD_Reg(0x814F,TouchData,count*8);	// 读取本次所有触摸点的数据
			}

			for (int i = 0; i < count; i++) {
				touch_Data[i].x = (TouchData[i*8 + 2] << 8) | TouchData[i*8 + 1];
				touch_Data[i].y = (TouchData[i*8 + 4] << 8) | TouchData[i*8 + 3];
				//xil_printf("x: %d , y:%d \n", touch_Data[i].x ,touch_Data[i].y);
			}
			touch_one_flag = (count>0 && count_pre ==0);
			touch_start_flag = (count > 0U);
			count_pre=count;
		}
		GT911_WR_Reg(0x814E,CleanData,1);	// 清除触摸数据就绪标志
		ToughFlag=0;
	}


// 原中断读写方案：读取触摸状态。
// 原中断读写方案：检查数据就绪位。
// 原中断读写方案：提取触摸点数。
// 原中断读写方案：读取触摸点数据。
// 原中断读写方案：清除数据就绪标志。
}

