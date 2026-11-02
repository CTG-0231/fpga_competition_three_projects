#ifndef __MESS_H
#define __MESS_H

#include "lcd.h"
#include "common.h"
#include "inference.h"
#include "pl_conv.h"
#include "xiltimer.h"

#define num_class 6
extern char trash[num_class][100];

/* 逻辑坐标与 LCD_DrawPoint 一致；按钮绘制/命中共用一套几何定义。
 * 原 API：宽=width*Font/2，高=ceil(len/width)*Font。
 */
#define CAMERA_UI_PREVIEW_X       16U
#define CAMERA_UI_PREVIEW_Y       16U
#define CAMERA_UI_BUTTON_X        488U
#define CAMERA_UI_DETECT_Y        220U
#define CAMERA_UI_DETECT_WIDTH    18U
#define CAMERA_UI_DETECT_LENGTH   36U
#define CAMERA_UI_DETECT_FONT     Font_32
#define CAMERA_UI_LIGHT_Y         300U
#define CAMERA_UI_SAVE_X          640U
#define CAMERA_UI_SAVE_Y          300U
#define CAMERA_UI_SMALL_WIDTH     17U
#define CAMERA_UI_SMALL_LENGTH    68U
#define CAMERA_UI_SMALL_FONT      Font_16
#define CAMERA_UI_IDLE            0U
#define CAMERA_UI_DETECTING       1U
#define CAMERA_UI_SAVING          2U

/** 页面只读数据：main 管理设备/操作状态，检测模块提供结果，绘制不操作硬件。
 * result_index=-1 表示无结果；elapsed_us 为上次推理耗时。
 * saved_count 仅统计本次启动成功写入 SD 的图片，重启从 0 开始。
 * message 由调用方持有，使用 ASCII，最多两行、每行 48 字符。
 */
typedef struct {
    uint8_t camera_ready;
    uint8_t detector_ready;
    uint8_t light_on;
    uint8_t busy;
    uint8_t error;             /* 1=本次操作/初始化失败，页脚使用醒目颜色。 */
    int result_index;
    uint32_t elapsed_us;
    uint32_t saved_count;
    const char *message;
} CameraUIState;

void ShowBotten(uint16_t x, uint16_t y, char *str, uint32_t color,
        uint32_t backcolor, uint8_t Font, uint8_t width, uint8_t len);
uint8_t Check_Botten(uint16_t x, uint16_t y, uint8_t width, uint8_t len,
        uint8_t Font);
void CameraUI_Draw(const CameraUIState *state);
int Detecting(short *image, NetParam_q *netParam, float *label, int N,
        short *out, int correct, u32 *elapsed_us);
/* 每次写一张 BMP，成功返回本次启动保存数量；失败返回 -1，数量不变。 */
int Camera_Sample(const uint8_t *image);

#endif
