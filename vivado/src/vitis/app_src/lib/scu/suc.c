#include "scu.h"
#include "hw_config.h"
XScuGic Intc; 
int SCU_Init(void)
{
    XScuGic_Config *IntcConfig;
    int Status;

    /* SDT 的查找键为 distributor 基地址，初始化仍传 CPU interface 地址。 */
    IntcConfig = XScuGic_LookupConfig(HW_GIC_BASEADDR);
    if (IntcConfig == NULL) {
        return XST_DEVICE_NOT_FOUND;
    }
    Status = XScuGic_CfgInitialize(&Intc, IntcConfig, IntcConfig->CpuBaseAddress);
    if (Status != XST_SUCCESS) {
        return Status;
    }
    Xil_ExceptionInit();
    Xil_ExceptionRegisterHandler(XIL_EXCEPTION_ID_INT,
                                 (Xil_ExceptionHandler)XScuGic_InterruptHandler,
                                 &Intc);
    Xil_ExceptionEnable();
    return XST_SUCCESS;
}
