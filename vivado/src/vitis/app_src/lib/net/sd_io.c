#include "sd_io.h"
#include <limits.h>

FATFS fatfs;

int SD_Init()
{
    FRESULT rc = f_mount(&fatfs, "", 0);
    if (rc != FR_OK) {
        xil_printf("ERROR : f_mount returned %d\r\n", rc);
        return XST_FAILURE;
    }
    return XST_SUCCESS;
}

/*****************************************************************************/
/**
 * Read exactly ByteLength bytes from the beginning of an existing SD file.
 *
 * @param FileName is the FatFs file path; it must not be NULL.
 * @param DestinationAddress is the 32-bit DDR address of the destination.
 * @param ByteLength is the number of bytes required by the caller.
 *
 * @return XST_SUCCESS only when all requested bytes were read and the file
 *         closed successfully; XST_INVALID_PARAM for invalid arguments;
 *         XST_FAILURE for open, seek, short-read, read, or close errors.
 *
 * @note A successfully opened file is closed on every subsequent exit path.
 *       A short weight file must never be accepted as a complete parameter.
 ******************************************************************************/
int SD_Transfer_read(char *FileName, u32 DestinationAddress, u32 ByteLength)
{
    FIL fil;
    FRESULT rc;
    FRESULT close_rc;
    UINT br = 0U;
    int status = XST_FAILURE;

    if (FileName == NULL || DestinationAddress == 0U) {
        return XST_INVALID_PARAM;
    }
    rc = f_open(&fil, FileName, FA_READ);
    if (rc != FR_OK) {
        xil_printf("ERROR : f_open returned %d\r\n", rc);
        return XST_FAILURE;
    }
    rc = f_lseek(&fil, 0);
    if (rc != FR_OK) {
        xil_printf("ERROR : f_lseek returned %d\r\n", rc);
    } else {
        rc = f_read(&fil, (void *)(UINTPTR)DestinationAddress,
                (UINT)ByteLength, &br);
        if (rc == FR_OK && br == ByteLength) {
            status = XST_SUCCESS;
        } else {
            xil_printf("ERROR : f_read returned %d, bytes %u/%u\r\n",
                    rc, (unsigned int)br, (unsigned int)ByteLength);
        }
    }
    close_rc = f_close(&fil);
    if (close_rc != FR_OK) {
        xil_printf("ERROR : f_close returned %d\r\n", close_rc);
        status = XST_FAILURE;
    }
    return status;
}

/*****************************************************************************/
/**
 * Write exactly ByteLength bytes to an SD file, replacing its old contents.
 *
 * @param FileName is the FatFs file path; its directory must already exist.
 * @param SourceAddress is the 32-bit DDR address of the source data.
 * @param ByteLength is the number of bytes to write.
 *
 * @return XST_SUCCESS only after the complete write and successful close;
 *         XST_INVALID_PARAM for invalid arguments; XST_FAILURE for any
 *         filesystem error or short write, including a full SD card.
 *
 * @note A successfully opened file is always closed. A failed write may leave
 *       a partial file; callers must not increment their saved-image count.
 ******************************************************************************/
int SD_Transfer_write(char *FileName, u32 SourceAddress, u32 ByteLength)
{
    FIL fil;
    FRESULT rc;
    FRESULT close_rc;
    UINT bw = 0U;
    int status = XST_FAILURE;

    if (FileName == NULL || SourceAddress == 0U) {
        return XST_INVALID_PARAM;
    }
    rc = f_open(&fil, FileName, FA_CREATE_ALWAYS | FA_WRITE);
    if (rc != FR_OK) {
        xil_printf("ERROR : f_open returned %d\r\n", rc);
        return XST_FAILURE;
    }
    rc = f_lseek(&fil, 0);
    if (rc != FR_OK) {
        xil_printf("ERROR : f_lseek returned %d\r\n", rc);
    } else {
        rc = f_write(&fil, (const void *)(UINTPTR)SourceAddress,
                (UINT)ByteLength, &bw);
        if (rc == FR_OK && bw == ByteLength) {
            status = XST_SUCCESS;
        } else {
            xil_printf("ERROR : f_write returned %d, bytes %u/%u\r\n",
                    rc, (unsigned int)bw, (unsigned int)ByteLength);
        }
    }
    close_rc = f_close(&fil);
    if (close_rc != FR_OK) {
        xil_printf("ERROR : f_close returned %d\r\n", close_rc);
        status = XST_FAILURE;
    }
    return status;
}

void read_param(float* buff,int length,const char* filename)
{
    printf("%s\n", filename);
    SD_Transfer_read((char *)filename, (u32)(UINTPTR)buff,
            (u32)(length * sizeof(float)));
}

/*****************************************************************************/
/**
 * Load one complete float32 parameter file and convert it to the existing
 * ten-fractional-bit short representation used by the accelerator.
 *
 * @param buff points to at least length destination short elements.
 * @param length is the positive number of float32 values required.
 * @param filename is the parameter file path.
 *
 * @return XST_SUCCESS after a complete load and conversion; XST_INVALID_PARAM
 *         for invalid arguments; XST_FAILURE for allocation or SD errors.
 *
 * @note The destination is unchanged on read failure. The temporary float
 *       allocation is released on every path; partial files are not converted.
 ******************************************************************************/
int read_param_q(short *buff, int length, const char *filename)
{
    float *tmp;
    int status;

    if (buff == NULL || filename == NULL || length <= 0 ||
            (u32)length > UINT_MAX / sizeof(float)) {
        return XST_INVALID_PARAM;
    }
    tmp = (float *)malloc(sizeof(float) * (size_t)length);
    if (tmp == NULL) {
        return XST_FAILURE;
    }
    status = SD_Transfer_read((char *)filename, (u32)(UINTPTR)tmp,
            (u32)((size_t)length * sizeof(float)));
    if (status == XST_SUCCESS) {
        for (int i = 0; i < length; ++i) {
            buff[i] = (short)(tmp[i] * FACTOR);
        }
    }
    free(tmp);
    return status;
}
