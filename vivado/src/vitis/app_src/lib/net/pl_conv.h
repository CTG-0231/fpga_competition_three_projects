#include <stdio.h>
#include "xil_printf.h"
#include"xpwdwconv.h"
#include"xil_cache.h"
#include"xparameters.h"
#include"xshortcut.h"
#include"xconv.h"
#include"xfc.h"

#ifndef SRC_PL_CONV_H_
#define SRC_PL_CONV_H_

extern XPwdwconv hls_pwdwconv;
extern XShortcut hls_shortcut;
extern XConv hls_conv;
extern XFc hls_fc;

short relu6(short x);
//第一个卷积层
int pl_conv_init(XConv *hls_inst);

void pl_conv(XConv hls_inst,short* in,short* weight,short* bias,short* out);
//残差连接
int pl_shortcut_init(XShortcut *hls_inst);

void pl_shortcut(XShortcut hls_inst,short* in1,short* in2,short* out,int length);
//pw卷积
int pl_pwdwconv_init(XPwdwconv *hls_inst);

void pl_pwconv(XPwdwconv hls_inst,short* in,short* weight,short* bias,short* out,int ch_in,int ch_out,int act,int size);
//dw卷积
//void pl_dwconv_init(XDwconv *hls_inst);

void pl_dwconv(XPwdwconv hls_inst,short* in,short* weight,short* bias,short* out,int channel,int size,int stride);

int pl_fc_init(XFc *hls_inst);

void pl_fc(XFc hls_inst,short* in,short* weight,short* bias,short* out);

#endif /* SRC_PL_CONV_H_ */
