

#define DEBUG_MODE		0

/******************** Include files **********************************/
#include "xaxivdma.h"
#include "xparameters.h"
#include "hw_config.h"
#include "xil_exception.h"

/******************** Data structure Declarations *****************************/

typedef struct vdma_handle
{
	/* The device ID of the VDMA */
	unsigned int device_id;
	/* The state variable to keep track if the initialization is done*/
	unsigned int init_done;
	/** The XAxiVdma driver instance data. */
	XAxiVdma* InstancePtr;
	/* The XAxiVdma_DmaSetup structure contains all the necessary information to
	 * start a frame write or read. */
	XAxiVdma_DmaSetup ReadCfg;
	XAxiVdma_DmaSetup WriteCfg;
	/* Horizontal size of frame */
	unsigned int hsize;
	/* Vertical size of frame */
	unsigned int vsize;
	/* Buffer address from where read and write will be done by VDMA */
	unsigned int buffer_address;
	/* Flag to tell VDMA to interrupt on frame completion*/
	unsigned int enable_frm_cnt_intr;
	/* The counter to tell VDMA on how many frames the interrupt should happen*/
	unsigned int number_of_frame_count;
}vdma_handle;

/******************** Constant Definitions **********************************/

/*
 * Device related constants. These need to defined as per the HW system.
 */
/* Keep a private context for the camera write channel.  The LCD API has a
 * separate context for its read channel; sharing the old global context made
 * the second initialization overwrite the first one's state. */
static vdma_handle ov5640_vdma_context[XPAR_XAXIVDMA_NUM_INSTANCES];
static unsigned int ov5640_context_init=0;

/******************* Function Prototypes ************************************/

static int WriteSetup(vdma_handle *vdma_context);
static int StartTransfer(XAxiVdma *InstancePtr);

/*****************************************************************************/
/**
*
* run_triple_frame_buffer API
*
* This API is the interface between application and other API. When application will call
* this API with right argument, This API will call rest of the API to configure the read
* and write path of VDMA,based on ID. After that it will start both the read and write path
* of VDMA
*
* @param	InstancePtr is the handle to XAxiVdma data structure.
* @param	InstanceIndex is the device ID of current VDMA
* @param	hsize is the horizontal size of the frame. It will be in Pixels.
* 		The actual size of frame will be calculated by multiplying this
* 		with tdata width.
* @param 	vsize is the Vertical size of the frame.
* @param	buf_base_addr is the buffer address where frames will be written
*		and read by VDMA.
* @param 	number_frame_count specifies after how many frames the interrupt
*		should come.
* @param 	enable_frm_cnt_intr is for enabling frame count interrupt
*		when set to 1.
* @return
*		- XST_SUCCESS if example finishes successfully
*		- XST_FAILURE if example fails.
*
******************************************************************************/
int run_triple_frame_buffer_ov5640(XAxiVdma* InstancePtr, int InstanceIndex, int hsize,
		int vsize, int buf_base_addr, int number_frame_count,
		int enable_frm_cnt_intr)
{
	int Status,i;
	XAxiVdma_Config *Config;
	XAxiVdma_FrameCounter FrameCfgPtr;

	/* This is one time initialization of state machine context.
	 * In first call it will be done for all VDMA instances in the system.
	 */
	if(ov5640_context_init==0) {
		for(i=0; i < XPAR_XAXIVDMA_NUM_INSTANCES; i++) {
			ov5640_vdma_context[i].InstancePtr = NULL;
			ov5640_vdma_context[i].device_id = -1;
			ov5640_vdma_context[i].hsize = 0;
			ov5640_vdma_context[i].vsize = 0;
			ov5640_vdma_context[i].init_done = 0;
			ov5640_vdma_context[i].buffer_address = 0;
			ov5640_vdma_context[i].enable_frm_cnt_intr = 0;
			ov5640_vdma_context[i].number_of_frame_count = 0;

		}
		ov5640_context_init = 1;
	}

	/* The below initialization will happen for each VDMA. The API argument
	 * will be stored in internal data structure
	 */

	/* The information of the XAxiVdma_Config comes from hardware build.
	 * The user IP should pass this information to the AXI DMA core.
	 */
	/* The context key is a bounded logical index, not an MMIO address. */
    if (InstancePtr == NULL || InstanceIndex != 0 ||
            InstanceIndex >= XPAR_XAXIVDMA_NUM_INSTANCES) {
        return XST_INVALID_PARAM;
    }
    Config = XAxiVdma_LookupConfig(HW_VDMA_BASEADDR);

	if (Config == NULL) {
		return XST_DEVICE_NOT_FOUND;
	}

	if(ov5640_vdma_context[InstanceIndex].init_done ==0) {
		ov5640_vdma_context[InstanceIndex].InstancePtr = InstancePtr;
		/* Initialize DMA engine */
		/* LCD_Init may already have initialized this same VDMA instance.  Do
		 * not call CfgInitialize a second time: it resets the MM2S channel. */
		if (InstancePtr->IsReady != XIL_COMPONENT_IS_READY) {
			Status = XAxiVdma_CfgInitialize(InstancePtr, Config,
					Config->BaseAddress);
			if (Status != XST_SUCCESS) {
				return Status;
			}
		}
		ov5640_vdma_context[InstanceIndex].init_done = 1;
	}

	ov5640_vdma_context[InstanceIndex].device_id = InstanceIndex;
	ov5640_vdma_context[InstanceIndex].vsize = vsize;
	ov5640_vdma_context[InstanceIndex].buffer_address = buf_base_addr;
	ov5640_vdma_context[InstanceIndex].enable_frm_cnt_intr = enable_frm_cnt_intr;
	ov5640_vdma_context[InstanceIndex].number_of_frame_count = number_frame_count;
	ov5640_vdma_context[InstanceIndex].hsize = hsize * (Config->Mm2SStreamWidth>>3);

	/* Setup the write channel */
	Status = WriteSetup(&ov5640_vdma_context[InstanceIndex]);
	if (Status != XST_SUCCESS) {
		xil_printf("Write channel setup failed %d\r\n", Status);
		if(Status == XST_VDMA_MISMATCH_ERROR)
			xil_printf("DMA Mismatch Error\r\n");
		return XST_FAILURE;
	}

	/* Setup the read channel */

	/* The frame counter interrupt is enabled, setting VDMA for same */
	if(ov5640_vdma_context[InstanceIndex].enable_frm_cnt_intr) {
		FrameCfgPtr.ReadDelayTimerCount = 1;
		FrameCfgPtr.ReadFrameCount = number_frame_count;
		FrameCfgPtr.WriteDelayTimerCount = 1;
		FrameCfgPtr.WriteFrameCount = number_frame_count;

		XAxiVdma_SetFrameCounter(ov5640_vdma_context[InstanceIndex].InstancePtr,&FrameCfgPtr);
		/* Enable DMA read and write channel interrupts. The configuration for interrupt
		 * controller will be done by application	 */
		XAxiVdma_IntrEnable(ov5640_vdma_context[InstanceIndex].InstancePtr,
				XAXIVDMA_IXR_ERROR_MASK |
				XAXIVDMA_IXR_FRMCNT_MASK,XAXIVDMA_WRITE);
	} else	{
		/* Enable DMA read and write channel interrupts. The configuration for interrupt
		* controller will be done by application	 */
		XAxiVdma_IntrEnable(ov5640_vdma_context[InstanceIndex].InstancePtr,
					XAXIVDMA_IXR_ERROR_MASK,XAXIVDMA_WRITE);
	}

	/* Start the DMA engine to transfer */
	Status = StartTransfer(ov5640_vdma_context[InstanceIndex].InstancePtr);
	if (Status != XST_SUCCESS) {
		if(Status == XST_VDMA_MISMATCH_ERROR)
			xil_printf("DMA Mismatch Error\r\n");
		return XST_FAILURE;
	}

	return XST_SUCCESS;
}

/*****************************************************************************/
/**
*
* This function sets up the write channel
*
* @param	dma_context is the context pointer to the VDMA engine..
*
* @return	XST_SUCCESS if the setup is successful, XST_FAILURE otherwise.
*
* @note		None.
*
******************************************************************************/
static int WriteSetup(vdma_handle *vdma_context)
{
	int Index;
	u32 Addr;
	int Status;

	vdma_context->WriteCfg.VertSizeInput = vdma_context->vsize;
	vdma_context->WriteCfg.HoriSizeInput = vdma_context->hsize;

	vdma_context->WriteCfg.Stride = vdma_context->hsize;
	vdma_context->WriteCfg.FrameDelay = 0;  /* This example does not test frame delay */

	vdma_context->WriteCfg.EnableCircularBuf = 1;
	vdma_context->WriteCfg.EnableSync = 1;  /*  Gen-Lock */

	vdma_context->WriteCfg.PointNum = 0;
	vdma_context->WriteCfg.EnableFrameCounter = 0; /* Endless transfers */

	vdma_context->WriteCfg.FixedFrameStoreAddr = 0; /* We are not doing parking */
	/* Configure the VDMA is per fixed configuration, This configuration
	 * is being used by majority of customers. Expert users can play around
	 * with this if they have different configurations
	 */

	Status = XAxiVdma_DmaConfig(vdma_context->InstancePtr, XAXIVDMA_WRITE, &vdma_context->WriteCfg);
	if (Status != XST_SUCCESS) {
		xil_printf("Write channel config failed %d\r\n", Status);
		return Status;
	}

	/* Initialize buffer addresses
	 *
	 * Use physical addresses
	 */
	Addr = vdma_context->buffer_address;
	/* If Debug mode is enabled write frame is shifted 3 Frames
	 * store ahead to compare read and write frames
	 */

	for(Index = 0; Index < vdma_context->InstancePtr->MaxNumFrames; Index++) {
		vdma_context->WriteCfg.FrameStoreStartAddr[Index] = Addr;
		Addr += (vdma_context->hsize * vdma_context->vsize);
	}

	/* Set the buffer addresses for transfer in the DMA engine */
	Status = XAxiVdma_DmaSetBufferAddr(vdma_context->InstancePtr,
			XAXIVDMA_WRITE,
			vdma_context->WriteCfg.FrameStoreStartAddr);
	if (Status != XST_SUCCESS) {
		xil_printf("Write channel set buffer address failed %d\r\n",
				Status);
		return XST_FAILURE;
	}

	return XST_SUCCESS;
}

/*****************************************************************************/
/**
*
* This function starts the DMA transfers. Since the DMA engine is operating
* in circular buffer mode, video frames will be transferred continuously.
*
* @param	InstancePtr points to the DMA engine instance
*
* @return
*		- XST_SUCCESS if both read and write start successfully
*		- XST_FAILURE if one or both directions cannot be started
*
* @note		None.
*
******************************************************************************/
static int StartTransfer(XAxiVdma *InstancePtr)
{
	int Status;
	/* Start the write channel of VDMA */
	Status = XAxiVdma_DmaStart(InstancePtr, XAXIVDMA_WRITE);

	return Status;
}
