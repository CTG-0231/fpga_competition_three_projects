#include"xil_io.h"
#include"pl_conv.h"
#include "hw_config.h"

XPwdwconv hls_pwdwconv;
XShortcut hls_shortcut;
XConv hls_conv;
XFc hls_fc;

short relu6(short x){
	if(x<0)
		return 0;
	else if(x>(6*1024))
		return (6*1024);
	else
		return x;
}

int pl_pwdwconv_init(XPwdwconv *hls_inst){
    int status = XPwdwconv_Initialize(hls_inst, TRASH_PWDWCONV_BASEADDR);
    if (status != XST_SUCCESS) {
        printf("initialize pwdwconv failed (%d)\n", status);
    }
    return status;
}

void pl_pwconv(XPwdwconv hls_inst,short* in,short* weight,short* bias,short* out,int ch_in,int ch_out,int act,int size)
{
    XPwdwconv_Set_PBUS1_V(&hls_inst, (u32)(UINTPTR)in);
	XPwdwconv_Set_PBUS2_V(&hls_inst, (u32)(UINTPTR)weight);
	XPwdwconv_Set_PBUS3_V(&hls_inst, (u32)(UINTPTR)weight);
	XPwdwconv_Set_PBUS4_V(&hls_inst, (u32)(UINTPTR)out);
	XPwdwconv_Set_SBUS1_V(&hls_inst, (u32)(UINTPTR)bias);
	XPwdwconv_Set_SBUS2_V(&hls_inst, (u32)(UINTPTR)bias);
	XPwdwconv_Set_ch_in(&hls_inst, (u32)ch_in);
	XPwdwconv_Set_ch_out(&hls_inst, (u32)ch_out);
	XPwdwconv_Set_stride(&hls_inst, (u32)1);
	XPwdwconv_Set_fsize(&hls_inst, (u32)size);
	XPwdwconv_Set_act(&hls_inst, (u32)act);
	XPwdwconv_Set_mode(&hls_inst, (u32)1);
	//
	XPwdwconv_Start(&hls_inst);
	while(XPwdwconv_IsDone(&hls_inst)==0);
}

//XDwconv hls_inst;
//void pl_dwconv_init(XDwconv *hls_inst){
//    if(XDwconv_Initialize(hls_inst, XPAR_DWCONV_0_DEVICE_ID)!=XST_SUCCESS){
//    	printf("initialize dwconv failed\n");
//    }
//    return;
//}

void pl_dwconv(XPwdwconv hls_inst,short* in,short* weight,short* bias,short* out,int channel,int size,int stride){
	XPwdwconv_Set_PBUS1_V(&hls_inst, (u32)(UINTPTR)in);
	XPwdwconv_Set_PBUS2_V(&hls_inst, (u32)(UINTPTR)in);
	XPwdwconv_Set_PBUS3_V(&hls_inst, (u32)(UINTPTR)out);
	XPwdwconv_Set_PBUS4_V(&hls_inst, (u32)(UINTPTR)out);
	XPwdwconv_Set_SBUS1_V(&hls_inst, (u32)(UINTPTR)weight);
	XPwdwconv_Set_SBUS2_V(&hls_inst, (u32)(UINTPTR)bias);
	XPwdwconv_Set_ch_in(&hls_inst, (u32)channel);
	XPwdwconv_Set_ch_out(&hls_inst, (u32)channel);
	XPwdwconv_Set_stride(&hls_inst, (u32)stride);
	XPwdwconv_Set_fsize(&hls_inst, (u32)size);
	XPwdwconv_Set_act(&hls_inst, (u32)1);
	XPwdwconv_Set_mode(&hls_inst, (u32)0);
	//
	XPwdwconv_Start(&hls_inst);
	while(XPwdwconv_IsDone(&hls_inst)==0);

}

int pl_shortcut_init(XShortcut *hls_inst){
    int status = XShortcut_Initialize(hls_inst, TRASH_SHORTCUT_BASEADDR);
    if (status != XST_SUCCESS) {
        printf("initialize shortcut failed (%d)\n", status);
    }
    return status;
}

void pl_shortcut(XShortcut hls_inst,short* in1,short* in2,short* out,int length){
	XShortcut_Set_src1_V(&hls_inst, (u32)(UINTPTR)in1);
	XShortcut_Set_src2_V(&hls_inst, (u32)(UINTPTR)in2);
	XShortcut_Set_dest_V(&hls_inst, (u32)(UINTPTR)out);
	XShortcut_Set_length_r(&hls_inst, (u32)length);
	XShortcut_Start(&hls_inst);
	while(XShortcut_IsDone(&hls_inst)==0);
}

int pl_conv_init(XConv *hls_inst){
    int status = XConv_Initialize(hls_inst, TRASH_CONV_BASEADDR);
    if (status != XST_SUCCESS) {
        printf("initialize conv failed (%d)\n", status);
    }
    return status;
}

void pl_conv(XConv hls_inst,short* in,short* weight,short* bias,short* out){
	XConv_Set_in1_V(&hls_inst, (u32)(UINTPTR)in);
	XConv_Set_in2_V(&hls_inst, (u32)(UINTPTR)in);
	XConv_Set_in3_V(&hls_inst, (u32)(UINTPTR)in);
	XConv_Set_weight_V(&hls_inst, (u32)(UINTPTR)weight);
	XConv_Set_bias_V(&hls_inst, (u32)(UINTPTR)bias);
	XConv_Set_out_V(&hls_inst, (u32)(UINTPTR)out);
	XConv_Start(&hls_inst);
    while(XConv_IsDone(&hls_inst)==0);
}

int pl_fc_init(XFc *hls_inst){
    int status = XFc_Initialize(hls_inst, TRASH_FC_BASEADDR);
    if (status != XST_SUCCESS) {
        printf("initialize fc failed (%d)\n", status);
    }
    return status;
}

void pl_fc(XFc hls_inst,short* in,short* weight,short* bias,short* out){
	XFc_Set_in_V(&hls_inst, (u32)(UINTPTR)in);
	XFc_Set_weight_V(&hls_inst, (u32)(UINTPTR)weight);
	XFc_Set_bias_V(&hls_inst, (u32)(UINTPTR)bias);
	XFc_Set_out_V(&hls_inst, (u32)(UINTPTR)out);
	XFc_Start(&hls_inst);
	while(XFc_IsDone(&hls_inst)==0);
}
