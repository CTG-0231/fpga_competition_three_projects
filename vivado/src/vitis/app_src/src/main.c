#include "common.h"
#include "lcd.h"
#include "uart.h"
#include "iic.h"
#include "ov5640.h"
#include "xil_printf.h"
#include "mess.h"
#include "camera_detection.h"

/* 调试彩条：0=正常图像，1=彩条，2=彩条滚动。 */
#define OV5640_TEST_PATTERN 0

int main(void)
{
    int status;
    int camera_status;
    CameraDetection detector;
    CameraUIState ui = {0};
    ui.result_index = -1;

    /* 设备层：继续使用原工程初始化顺序及 API。 */
    status = SCU_Init();
    if (status != XST_SUCCESS) return status;
    status = UART_Intr_Init(&UartPs1, &Intc, HW_UART1_BASEADDR,
            115200, HW_UART1_INTR_ID);
    if (status != XST_SUCCESS) return status;
    status = IIC_Init(&IicPs1, HW_IIC1_BASEADDR, 100000);
    if (status != XST_SUCCESS) return status;
    status = IIC_Init(&IicPs0, HW_IIC0_BASEADDR, 300000);
    if (status != XST_SUCCESS) return status;
    status = LCD_Init();
    if (status != XST_SUCCESS) {
        UART_Print("LCD init failed: %d\r\n", status);
        return status;
    }
    status = LCD_Touch_Init();
    if (status != XST_SUCCESS) return status;
    status = IIC_Itr_Init(&IicPs0, HW_IIC0_BASEADDR, 300000);
    if (status != XST_SUCCESS) return status;

    /* 先显示状态，再执行可能较慢的相机/SD 权重初始化。 */
    ui.message = "Starting camera...";
    CameraUI_Draw(&ui);
    camera_status = OV5640_Init();
#if OV5640_TEST_PATTERN
    if (camera_status == XST_SUCCESS) {
        (void)OV5640_SetTestPattern(OV5640_TEST_PATTERN);
        usleep(100000U);
    }
#endif
    ui.camera_ready = camera_status == XST_SUCCESS;
    /* 模型加载期间也先显示相机帧，清除启动时的离线占位。 */
    if (ui.camera_ready) (void)OV5640_ShowFrame();
    ui.message = "Loading model from SD card...";
    CameraUI_Draw(&ui);
    status = CameraDetection_Init(&detector);
    ui.detector_ready = status == XST_SUCCESS;
    if (!ui.camera_ready) {
        ui.error = 1U;
        ui.message = "Camera offline. Check connection.";
    } else if (!ui.detector_ready) {
        ui.error = 1U;
        ui.message = "Model unavailable. Check trash_weight.\nPreview, light and save remain available.";
        UART_Print("Model unavailable; preview/save remain available\r\n");
    } else {
        ui.message = "Place one leaf in view, then tap DETECT.";
    }
    if (ui.camera_ready && OV5640_Light_Turn_Off() != XST_SUCCESS) {
        ui.error = 1U;
        ui.message = "Light setup failed. Check camera IIC.";
    }
    CameraUI_Draw(&ui);

    while (1) {
        /* 显示层：只刷新预览，按钮/结果仅在状态改变时重绘，减少闪烁。 */
        if (ui.camera_ready) (void)OV5640_ShowFrame();
        Check_Touch();
        if (touch_start_flag && touch_one_flag) {
            uint8_t detect = Check_Botten(CAMERA_UI_BUTTON_X, CAMERA_UI_DETECT_Y,
                    CAMERA_UI_DETECT_WIDTH, CAMERA_UI_DETECT_LENGTH,
                    CAMERA_UI_DETECT_FONT);
            uint8_t light = Check_Botten(CAMERA_UI_BUTTON_X, CAMERA_UI_LIGHT_Y,
                    CAMERA_UI_SMALL_WIDTH, CAMERA_UI_SMALL_LENGTH,
                    CAMERA_UI_SMALL_FONT);
            uint8_t save = Check_Botten(CAMERA_UI_SAVE_X, CAMERA_UI_SAVE_Y,
                    CAMERA_UI_SMALL_WIDTH, CAMERA_UI_SMALL_LENGTH,
                    CAMERA_UI_SMALL_FONT);
            /* 消费按下边沿：长按不重复触发，一个触点只执行一个动作。 */
            touch_start_flag = 0U;
            touch_one_flag = 0U;
            if (detect || light || save) ui.error = 0U;
            if (detect) {
                if (!ui.camera_ready || !ui.detector_ready) {
                    ui.error = 1U;
                    ui.message = !ui.camera_ready ? "Camera is not ready." :
                            "Model unavailable. Check trash_weight.";
                } else {
                    ui.busy = CAMERA_UI_DETECTING;
                    ui.message = "Analyzing this frame. Please wait...";
                    CameraUI_Draw(&ui);
                    status = CameraDetection_Run(&detector);
                    ui.busy = CAMERA_UI_IDLE;
                    if (status == XST_SUCCESS) {
                        ui.result_index = detector.result_index;
                        ui.elapsed_us = detector.elapsed_us;
                        ui.message = "Detection complete. Last result is shown.";
                    } else {
                        ui.error = 1U;
                        ui.message = "Detection failed. Check UART diagnostics.";
                    }
                }
            } else if (light) {
                if (!ui.camera_ready) {
                    ui.error = 1U;
                    ui.message = "Camera is not ready.";
                } else {
                    status = ui.light_on ? OV5640_Light_Turn_Off() :
                            OV5640_Light_Turn_On();
                    if (status == XST_SUCCESS) {
                        ui.light_on = !ui.light_on;
                        ui.message = ui.light_on ? "Light assist enabled." :
                                "Light assist disabled.";
                    } else {
                        ui.error = 1U;
                        ui.message = "Light command failed. Check camera IIC.";
                    }
                }
            } else if (save) {
                if (!ui.camera_ready) {
                    ui.error = 1U;
                    ui.message = "Camera is not ready.";
                } else {
                    int saved;
                    ui.busy = CAMERA_UI_SAVING;
                    ui.message = "Writing image to SD. Please wait...";
                    CameraUI_Draw(&ui);
                    saved = Camera_Sample(OV5640_GetRawFrame());
                    ui.busy = CAMERA_UI_IDLE;
                    if (saved > 0) {
                        ui.saved_count = (uint32_t)saved;
                        ui.message = "Image saved as BMP in SD:/Test.";
                    } else {
                        ui.error = 1U;
                        ui.message = "Save failed. Check SD card/free space.";
                    }
                }
            }
            if (detect || light || save) {
                CameraUI_Draw(&ui);
                /* 丢弃耗时操作期间积压的触摸，必须松开再按才能触发下一次。 */
                Check_Touch();
                touch_start_flag = 0U;
                touch_one_flag = 0U;
            }
        }
        usleep(33000U);
    }
    return 0;
}
