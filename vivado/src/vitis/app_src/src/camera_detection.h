#ifndef CAMERA_DETECTION_H
#define CAMERA_DETECTION_H

#include "common.h"
#include "mess.h"

typedef struct {
    int ready;
    int batch_size;
    NetParam_q *net_param;
    short *image;
    short *output;
    /* Last completed result; -1 means that no valid detection is available. */
    int result_index;
    u32 elapsed_us;
} CameraDetection;

int CameraDetection_Init(CameraDetection *detector);
/* Fills image from the camera, then records result_index and elapsed_us. */
int CameraDetection_Run(CameraDetection *detector);

#endif
