#include "mess.h"
#include <string.h>
#include "sd_io.h"
#include "hw_config.h"

/* 配色只在此处调整；布局定义在 mess.h，不改变底层 LCD API。 */
#define UI_PANEL        0x00101F2BU
#define UI_CARD         0x001C3040U
#define UI_BORDER       0x002D4859U
#define UI_TEXT         0x00E9F2F2U
#define UI_MUTED        0x0095AEBEU
#define UI_ACCENT       0x001FB69BU
#define UI_DISABLED     0x00283E4CU
#define UI_AMBER        0x00B77929U
#define CAMERA_SAMPLE_BYTES (3U * 224U * 224U)
#define CAMERA_BMP_HEADER   54U
#define CAMERA_FILE_LIMIT   99999U

/* 沿用原采集 DDR 区。只使用 54+150528 字节，不再积攒 50 张。 */
static uint8_t *const camera_sample_buffer = (uint8_t *)HW_SAMPLE_BUFFER_ADDR;
static uint32_t camera_sample_count = 0U;
static uint32_t camera_file_index = 1U;
char trash[num_class][100] = {"healthy", "bacterial_leaf_blight", "brown_spot",
        "leaf_blast", "leaf_scald", "narrow_brown"};

/*****************************************************************************/
/**
 * 沿用原按钮字符网格，区域填充复用 LCD_CleanArea。
 *
 * @param x,y       按钮左上角逻辑坐标。
 * @param str       ASCII 标签，可短于 len，剩余位置保持背景。
 * @param color     文字 RGB888 颜色。
 * @param backcolor 按钮 RGB888 背景。
 * @param Font      原字库字号。
 * @param width     每行字符数，非零。
 * @param len       字符网格总长度，决定按钮高度。
 *
 * @return None.
 * @note 不刷新帧缓冲，由调用方在整页绘制后统一 LCD_Refresh。
 *****************************************************************************/
void ShowBotten(uint16_t x, uint16_t y, char *str, uint32_t color,
        uint32_t backcolor, uint8_t Font, uint8_t width, uint8_t len)
{
    uint16_t total_width;
    uint16_t total_height;
    size_t text_length;
    if (str == NULL || width == 0U || Font == 0U || len == 0U) return;
    total_width = width * Font / 2U;
    total_height = Font * ((len + width - 1U) / width);
    LCD_CleanArea(x, y, total_width, total_height, backcolor);
    text_length = strlen(str);
    for (unsigned int i = 0U; i < len && i < text_length; ++i) {
        if (str[i] >= ' ' && str[i] <= '~') {
            LCD_ShowChar(str[i], x + (i % width) * Font / 2U,
                    y + (i / width) * Font, Font, color);
        }
    }
}

/*****************************************************************************/
/**
 * 复用原触摸数据与字符网格判断命中，不消费事件、不修改检测标志。
 *
 * @param x,y   与 ShowBotten 一致的逻辑左上角。
 * @param width 每行字符数。
 * @param len   字符网格总长度。
 * @param Font  原字库字号。
 *
 * @return 位于按钮内返回 1，否则返回 0。
 * @note 翻转与 LCD_DrawPoint 严格互逆；右/下边界不包含在按钮内。
 *       main 用 touch_one_flag 保证一次按下只执行一次。
 *****************************************************************************/
uint8_t Check_Botten(uint16_t x, uint16_t y, uint8_t width, uint8_t len,
        uint8_t Font)
{
    uint16_t touch_x;
    uint16_t touch_y;
    uint32_t total_width;
    uint32_t total_height;
    if (!touch_start_flag || width == 0U || Font == 0U || len == 0U ||
            touch_Data[0].x >= LCD_W || touch_Data[0].y >= LCD_H) return 0U;
    touch_x = touch_Data[0].x;
    touch_y = touch_Data[0].y;
#if LCD_FLIP_DISPLAY
    touch_x = LCD_W - 1U - touch_x;
    touch_y = LCD_H - 1U - touch_y;
#endif
    total_width = width * Font / 2U;
    total_height = Font * ((len + width - 1U) / width);
    return touch_x >= x && touch_x < x + total_width &&
            touch_y >= y && touch_y < y + total_height;
}

/*****************************************************************************/
/**
 * 绘制 800x480 页面：左侧 448x448 预览，右侧结果/按钮/保存计数。
 *
 * @param state 只读页面状态，NULL 时不绘制。message 存储由调用方持有。
 *
 * @return None.
 * @note 本次唯一新增的页面函数。首次绘制背景和边框，后续仅在状态改变
 *       时重绘右侧，不在预览循环重画按钮。相机显示仍由 OV5640_ShowFrame
 *       负责。本函数不取图、不检测、不保存、不控制补光。
 *       末尾 LCD_Refresh 保证阻塞检测/写卡前忙碌提示可见。
 *       字库只有 ASCII，标签沿用英文。几何布局见 mess.h。
 *****************************************************************************/
void CameraUI_Draw(const CameraUIState *state)
{
    static uint8_t background_drawn = 0U;
    static const char *const result_names[num_class] = {
        "Healthy", "Bacterial blight", "Brown spot", "Leaf blast",
        "Leaf scald", "Narrow brown spot"
    };
    const char *detect_text;
    const char *detect_caption;
    uint32_t button_color;
    if (state == NULL) return;

    /* 静态层：原绘图 API 生成背景，无外部位图/SD 解码依赖。 */
    if (background_drawn == 0U) {
        for (uint16_t y = 0U; y < LCD_H; ++y) {
            LCD_CleanArea(0U, y, LCD_W, 1U,
                    Gen_Color(10U + y / 40U, 21U + y / 30U, 32U + y / 24U));
        }
        LCD_CleanArea(10U, 10U, 460U, 460U, 0x00081119U);
        LCD_CleanArea(13U, 13U, 454U, 454U, UI_BORDER);
        LCD_CleanArea(CAMERA_UI_PREVIEW_X, CAMERA_UI_PREVIEW_Y,
                448U, 448U, UI_PANEL);
        LCD_CleanArea(10U, 10U, 70U, 3U, UI_ACCENT);
        LCD_CleanArea(400U, 467U, 70U, 3U, UI_ACCENT);
        background_drawn = 1U;
    }
    if (!state->camera_ready) {
        LCD_CleanArea(CAMERA_UI_PREVIEW_X, CAMERA_UI_PREVIEW_Y,
                448U, 448U, UI_PANEL);
        LCD_Print(116U, 204U, Font_24, UI_PANEL, UI_TEXT, "CAMERA OFFLINE");
        LCD_Print(98U, 244U, Font_16, UI_PANEL, UI_MUTED,
                "Check camera connection");
    }

    /* 结果层：明确是上次检测结果，预览刷新不擦除结果。 */
    LCD_CleanArea(480U, 16U, 304U, 448U, UI_PANEL);
    LCD_Print(488U, 24U, Font_24, UI_PANEL, UI_TEXT, "LEAF VISION");
    LCD_Print(488U, 58U, Font_12, UI_PANEL, UI_MUTED, "%s",
            state->camera_ready ? "LIVE VIEW  /  224 x 224" : "PREVIEW  /  UNAVAILABLE");
    LCD_Print(704U, 32U, Font_12, UI_PANEL,
            state->camera_ready && state->detector_ready ? UI_ACCENT : UI_MUTED,
            "%s", !state->camera_ready ? "NO CAMERA" :
                    (!state->detector_ready ? "NO MODEL" :
                            (state->busy ? "WORKING" : "READY")));
    LCD_CleanArea(488U, 82U, 288U, 1U, UI_BORDER);
    LCD_CleanArea(488U, 96U, 288U, 110U, UI_CARD);
    LCD_CleanArea(488U, 96U, 3U, 110U, UI_ACCENT);
    LCD_Print(502U, 106U, Font_12, UI_CARD, UI_MUTED, "LAST DETECTION");
    if (state->result_index >= 0 && state->result_index < num_class) {
        LCD_Print(502U, 132U, Font_24, UI_CARD, UI_TEXT, "%s",
                result_names[state->result_index]);
        LCD_Print(502U, 166U, Font_12, UI_CARD, UI_MUTED, "%s",
                trash[state->result_index]);
        LCD_Print(502U, 186U, Font_12, UI_CARD, UI_ACCENT, "INFERENCE  %lu ms",
                (unsigned long)(state->elapsed_us / 1000U));
    } else {
        LCD_Print(502U, 132U, Font_24, UI_CARD, UI_TEXT, "No result yet");
        LCD_Print(502U, 172U, Font_12, UI_CARD, UI_MUTED, "%s",
                state->detector_ready ? "Tap DETECT to inspect a leaf" :
                        "Load model files on the SD card");
    }

    /* 按钮层：复用 ShowBotten，每行填满原字符网格。 */
    detect_text = state->busy == CAMERA_UI_DETECTING ?
            "   ANALYZING...   " "                  " :
            "      DETECT      " "                  ";
    detect_caption = state->busy ? "Please wait" :
            (!state->camera_ready ? "Camera offline" :
                    (!state->detector_ready ? "Model unavailable" : "Analyze a leaf"));
    button_color = state->camera_ready && state->detector_ready &&
            state->busy == CAMERA_UI_IDLE ? UI_ACCENT : UI_DISABLED;
    ShowBotten(CAMERA_UI_BUTTON_X, CAMERA_UI_DETECT_Y, (char *)detect_text,
            button_color == UI_ACCENT ? UI_PANEL : UI_TEXT,
            button_color, CAMERA_UI_DETECT_FONT,
            CAMERA_UI_DETECT_WIDTH, CAMERA_UI_DETECT_LENGTH);
    LCD_Print((uint16_t)(632U - strlen(detect_caption) * Font_16 / 4U),
            260U, Font_16, button_color,
            button_color == UI_ACCENT ? UI_PANEL : UI_MUTED, "%s", detect_caption);
    ShowBotten(CAMERA_UI_BUTTON_X, CAMERA_UI_LIGHT_Y,
            state->light_on ?
            "                 " "  LIGHT ASSIST   " "       ON        " "                 " :
            "                 " "  LIGHT ASSIST   " "       OFF       " "                 ",
            UI_TEXT, !state->camera_ready || state->busy ? UI_DISABLED :
                    (state->light_on ? UI_AMBER : UI_CARD),
            CAMERA_UI_SMALL_FONT, CAMERA_UI_SMALL_WIDTH, CAMERA_UI_SMALL_LENGTH);
    ShowBotten(CAMERA_UI_SAVE_X, CAMERA_UI_SAVE_Y,
            state->busy == CAMERA_UI_SAVING ?
            "                 " "    SAVING...    " "   Please wait   " "                 " :
            "                 " "   SAVE IMAGE    " "    SD / BMP     " "                 ",
            UI_TEXT, state->camera_ready && !state->busy ? UI_CARD : UI_DISABLED,
            CAMERA_UI_SMALL_FONT, CAMERA_UI_SMALL_WIDTH, CAMERA_UI_SMALL_LENGTH);

    /* 反馈层：仅显示已完整写入 SD 的图片数量。 */
    LCD_CleanArea(488U, 380U, 288U, 48U, UI_CARD);
    LCD_Print(500U, 390U, Font_12, UI_CARD, UI_MUTED, "SAVED THIS SESSION");
    LCD_Print(696U, 386U, Font_32, UI_CARD, UI_TEXT, "%5lu",
            (unsigned long)state->saved_count);
    if (state->message != NULL) {
        LCD_Print(488U, 440U, Font_12, UI_PANEL,
                state->error ? 0x00FFC383U : UI_MUTED, "%s", state->message);
    }
    LCD_Refresh();
}

/*****************************************************************************/
/**
 * 复用原推理、计时和 argmax，返回结果给调用者，不再在固定坐标绘制。
 *
 * @param image,netParam,out 原输入/参数/六类输出缓冲。
 * @param label,correct     保留原参数，本页面不使用。
 * @param N                 图片数，必须大于零，页面调用为 1。
 * @param elapsed_us        可选输出，最后一张图片推理微秒数。
 *
 * @return 最后一张图片类别索引；无效参数返回 -1。
 * @note 原始定点分数不当作概率；显示统一由 CameraUI_Draw 负责。
 *****************************************************************************/
int Detecting(short *image, NetParam_q *netParam, float *label, int N,
        short *out, int correct, u32 *elapsed_us)
{
    XTime end;
    XTime start;
    int max_idx = -1;
    (void)label;
    (void)correct;
    if (elapsed_us != NULL) *elapsed_us = 0U;
    if (image == NULL || netParam == NULL || out == NULL || N <= 0) return -1;
    for (int i = 0; i < N; ++i) {
        u32 used;
        int max_value = -32768;
        XTime_GetTime(&start);
        inference_q(image + i * 3 * 224 * 224, netParam, out, num_class);
        XTime_GetTime(&end);
        used = (u32)(((end - start) * 1000000ULL) / COUNTS_PER_SECOND);
        if (elapsed_us != NULL) *elapsed_us = used;
        xil_printf("total time elapsed is %lu us\r\n", (unsigned long)used);
        xil_printf("scores:");
        max_idx = 0;
        for (int k = 0; k < num_class; ++k) {
            xil_printf(" %d", out[k]);
            if (out[k] > max_value) {
                max_value = out[k];
                max_idx = k;
            }
        }
        xil_printf("\r\npredict result:%s\r\n", trash[max_idx]);
    }
    return max_idx;
}

/*****************************************************************************/
/**
 * 当前一帧立即保存为 PC 可查看的 24 位 BMP，复用原采集缓冲和 SD API。
 *
 * @param image 224x224 交错 BGR888 只读图像，调用方通过原
 *              OV5640_GetRawFrame 获取并完成源缓存失效。
 *
 * @return 本次启动累计成功保存数量（大于零）；失败返回 -1，数量不变。
 * @note 文件为 Test/IMG00001.BMP 至 IMG99999.BMP；f_stat 跳过已有文件，
 *       重启后也不覆盖。此程序是 SD 的唯一写入者。
 *       BMP 负高度保留原 BGR 行序，224*3 已四字节对齐。
 *       仅在完整写入和关闭后增加计数，文件号不等于本次启动计数。
 *       原单帧 DMA 未冻结，此快照不承诺无撕裂采集。
 *****************************************************************************/
int Camera_Sample(const uint8_t *image)
{
    static const uint8_t bmp_header[CAMERA_BMP_HEADER] = {
        /* BITMAPFILEHEADER: signature, size, reserved, pixel offset (14 B). */
        0x42,0x4D,0x36,0x4C,0x02,0x00,0x00,0x00,0x00,0x00,0x36,0x00,0x00,0x00,
        /* BITMAPINFOHEADER (40 B): 224 x -224, 1 plane, 24-bit BGR. */
        0x28,0x00,0x00,0x00,
        0xE0,0x00,0x00,0x00,
        0x20,0xFF,0xFF,0xFF,
        0x01,0x00,0x18,0x00,
        0x00,0x00,0x00,0x00,
        0x00,0x4C,0x02,0x00,
        0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00
    };
    char filename[32];
    FILINFO info;
    FRESULT rc;
    if (image == NULL || SD_Init() != XST_SUCCESS) return -1;
    rc = f_mkdir("Test");
    if (rc != FR_OK && rc != FR_EXIST) return -1;
    while (camera_file_index <= CAMERA_FILE_LIMIT) {
        (void)snprintf(filename, sizeof(filename), "Test/IMG%05lu.BMP",
                (unsigned long)camera_file_index);
        rc = f_stat(filename, &info);
        if (rc == FR_NO_FILE) break;
        if (rc != FR_OK) return -1;
        ++camera_file_index;
    }
    if (camera_file_index > CAMERA_FILE_LIMIT) return -1;
    memcpy(camera_sample_buffer, bmp_header, CAMERA_BMP_HEADER);
    memcpy(camera_sample_buffer + CAMERA_BMP_HEADER, image, CAMERA_SAMPLE_BYTES);
    if (SD_Transfer_write(filename, (u32)(UINTPTR)camera_sample_buffer,
            CAMERA_BMP_HEADER + CAMERA_SAMPLE_BYTES) != XST_SUCCESS) {
        xil_printf("Image save failed: %s\r\n", filename);
        return -1;
    }
    ++camera_sample_count;
    ++camera_file_index;
    xil_printf("Image saved: %s (%lu this session)\r\n", filename,
            (unsigned long)camera_sample_count);
    return (int)camera_sample_count;
}
