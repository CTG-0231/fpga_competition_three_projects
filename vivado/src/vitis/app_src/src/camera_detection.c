#include "camera_detection.h"
#include "ov5640.h"
#include "uart.h"
#include "sd_io.h"
#include "pl_conv.h"

#define CAMERA_INPUT_ELEMENTS (3U * 224U * 224U)

/*****************************************************************************/
/**
 * Initialize accelerator instances, image storage, and all model parameters.
 *
 * @param detector points to a fresh, uninitialized CameraDetection object.
 *
 * @return XST_SUCCESS only after every weight file loaded completely;
 *         XST_INVALID_PARAM for a NULL object; XST_FAILURE for SD, driver,
 *         allocation, or parameter-load failure.
 *
 * @note No inference is performed here. On failure, ready remains zero and
 *       allocated storage is released, so the UI can keep preview available
 *       while displaying that the model is unavailable.
 ******************************************************************************/
int CameraDetection_Init(CameraDetection *detector)
{
    if (detector == NULL) {
        return XST_INVALID_PARAM;
    }

    memset(detector, 0, sizeof(*detector));
    detector->batch_size = 1;
    detector->result_index = -1;
    if (SD_Init() != XST_SUCCESS) {
        return XST_FAILURE;
    }

    /* Stop before any HLS register access if an instance is not initialized. */
    if (pl_pwdwconv_init(&hls_pwdwconv) != XST_SUCCESS ||
            pl_shortcut_init(&hls_shortcut) != XST_SUCCESS ||
            pl_conv_init(&hls_conv) != XST_SUCCESS ||
            pl_fc_init(&hls_fc) != XST_SUCCESS) {
        return XST_FAILURE;
    }

    detector->net_param = (NetParam_q *)calloc(1U, sizeof(NetParam_q));
    detector->image = (short *)malloc(sizeof(short) * CAMERA_INPUT_ELEMENTS);
    detector->output = (short *)malloc(sizeof(short) * num_class);
    if (detector->net_param == NULL || detector->image == NULL ||
            detector->output == NULL) {
        free(detector->net_param);
        free(detector->image);
        free(detector->output);
        detector->net_param = NULL;
        detector->image = NULL;
        detector->output = NULL;
        return XST_FAILURE;
    }

    SpaceAllocateq(detector->net_param, num_class);
    if (ReadParamq("trash_weight\\", detector->net_param, num_class)
            != XST_SUCCESS) {
        SpaceDeleteq(detector->net_param);
        free(detector->image);
        free(detector->output);
        detector->net_param = NULL;
        detector->image = NULL;
        detector->output = NULL;
        return XST_FAILURE;
    }
    Xil_DCacheFlush();
    detector->ready = 1;
    return XST_SUCCESS;
}

/*****************************************************************************/
/**
 * Capture the current camera input and run the existing detection pipeline.
 *
 * @param detector points to an object initialized by CameraDetection_Init().
 *
 * @return XST_SUCCESS when a valid class index was returned by Detecting();
 *         XST_FAILURE if the detector is unavailable or detection fails.
 *
 * @note Records the class and inference time without drawing on the LCD.
 *       The UI owns presentation and may label this as the last detection.
 ******************************************************************************/
int CameraDetection_Run(CameraDetection *detector)
{
    if (detector == NULL || detector->ready == 0 || detector->image == NULL ||
            detector->net_param == NULL || detector->output == NULL) {
        return XST_FAILURE;
    }

    /* 先将摄像头采集缓冲转换并搬运到detector->image，同时处理缓存同步。 */
    OV5640_GetInferenceFrame(detector->image);
    /* 再把本次搬运得到的图像交给检测函数，不能只分配输入内存而不填充。 */
    detector->result_index = Detecting(detector->image, detector->net_param,
            NULL, detector->batch_size, detector->output, 0,
            &detector->elapsed_us);
    return detector->result_index >= 0 ? XST_SUCCESS : XST_FAILURE;
}
