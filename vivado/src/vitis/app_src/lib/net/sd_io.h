#ifndef TRASH_SD_IO_H
#define TRASH_SD_IO_H

#include "ff.h"
#include "xparameters.h"
#include "xil_types.h"
#include "xstatus.h"
#include "xil_printf.h"
#include"stdio.h"
#include"stdlib.h"
/* HLS使用十位小数，权重和偏置必须按1024缩放后写入。 */
#define FACTOR 1024
#define MAX 31
#define MIN -32
#define UP 32767
#define DOWN -32768

extern FATFS fatfs;

int SD_Init();

int SD_Transfer_read(char *FileName,u32 DestinationAddress,u32 ByteLength);

int SD_Transfer_write(char *FileName,u32 SourceAddress,u32 ByteLength);

void read_param(float* buff,int length,const char* filename);

/* Returns XST_SUCCESS only after a complete float32 load and conversion. */
int read_param_q(short* buff,int length,const char* filename);

#endif /* TRASH_SD_IO_H */
