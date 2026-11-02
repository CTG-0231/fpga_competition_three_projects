#include"layer.h"
#include <malloc.h>
#include <limits.h>

void Bottlenecksq(short* in,BottleneckParam_q *param,short* out,Cfg_q config){
    //(in_channel,h,w)--->(mid_channel,h,w)---->(mid_channel,h,w)
    int stride=config.stride;
    int h=config.h;
    int w=config.w;
    int in_channel=config.ch_in;
    int mid_channel=config.ch_mid;
    int out_channel=config.ch_out;
    short* wc1=param->Wc1;
    short* bc1=param->bc1;
    short* wc2=param->Wc2;
    short* bc2=param->bc2;
    short* wc3=param->Wc3;
    short* bc3=param->bc3;
    //
    static short __attribute__((aligned(8))) tmp1[1500000];
    static short __attribute__((aligned(8))) tmp2[1500000];
    static short __attribute__((aligned(8))) tmp3[1500000];
    //
    pl_pwconv(hls_pwdwconv,in,wc1,bc1,tmp1,in_channel,mid_channel,1,h);
    pl_dwconv(hls_pwdwconv,tmp1,wc2,bc2,tmp2,mid_channel,h,stride);
    if(stride==1){
    	if(in_channel!=out_channel){
    		pl_pwconv(hls_pwdwconv,tmp2,wc3,bc3,out,mid_channel,out_channel,0,h);
    	}
    	else{
    		pl_pwconv(hls_pwdwconv,tmp2,wc3,bc3,tmp3,mid_channel,out_channel,0,h);
    		pl_shortcut(hls_shortcut,tmp3,in,out,out_channel*h*w);
    	}
    }
    else
    	pl_pwconv(hls_pwdwconv,tmp2,wc3,bc3,out,mid_channel,out_channel,0,h/2);
}

void Headq(short* in,HeadParam_q *param,short* out){
    //(3,224,224)--->(32,112,112)---->(32,112,112)---->(16,112,112)
    short* wc1=param->Wc1;
    short* bc1=param->bc1;
    short* wc2=param->Wc2;
    short* bc2=param->bc2;
    short* wc3=param->Wc3;
    short* bc3=param->bc3;
    static short __attribute__((aligned(8))) tmp1[112*112*32];
    static short __attribute__((aligned(8))) tmp2[112*112*32];
    pl_conv(hls_conv,in,wc1,bc1,tmp1);
    pl_dwconv(hls_pwdwconv,tmp1,wc2,bc2,tmp2,32,112,1);
    pl_pwconv(hls_pwdwconv,tmp2,wc3,bc3,out,32,16,0,112);
}

void Tailq(short* in,TailParam_q *param,short* out,int num_class){
    short* wc1=param->Wc1;
    short* bc1=param->bc1;
    short* wf1=param->Wf1;
    short* bf1=param->bf1;
    static short __attribute__((aligned(8))) tmp1[1280*7*7];
    pl_pwconv(hls_pwdwconv,in,wc1,bc1,tmp1,320,1280,1,7);
    pl_fc(hls_fc,tmp1,wf1,bf1,out);
    Xil_DCacheInvalidateRange((u32)((unsigned int)out&0xffffffe0),32*((num_class*sizeof(short))/32+2));
}


/*******************************************************************************************************/
char* stringcat_q(char* a,char* b){
    char* result=(char*)malloc(sizeof(char)*100);
    strcpy(result,a);
    strcat(result,b);
    return result;
}

void SpaceAllocateq(NetParam_q* netParam,int num_class){
    Cfg_q cfg[16]={{16,96,24,112,112,2},
                          {24,144,24,56,56,1},
                          {24,144,32,56,56,2},
                          {32,192,32,28,28,1},
                          {32,192,32,28,28,1},
                          {32,192,64,28,28,2},
                          {64,384,64,14,14,1},
                          {64,384,64,14,14,1},
                          {64,384,64,14,14,1},
                          {64,384,96,14,14,1},
                          {96,576,96,14,14,1},
                          {96,576,96,14,14,1},
                          {96,576,160,14,14,2},
                          {160,960,160,7,7,1},
                          {160,960,160,7,7,1},
                          {160,960,320,7,7,1}};
    //head
    netParam->headParam.Wc1=(short*)memalign(8,32*3*3*3*sizeof(short));
    netParam->headParam.bc1=(short*)memalign(8,32*sizeof(short));
    netParam->headParam.Wc2=(short*)memalign(8,32*1*3*3*sizeof(short));
    netParam->headParam.bc2=(short*)memalign(8,32*sizeof(short));
    netParam->headParam.Wc3=(short*)memalign(8,32*16*1*1*sizeof(short));
    netParam->headParam.bc3=(short*)memalign(8,16*sizeof(short));
    //bottle
    for(int i=0;i<16;i++){
        netParam->bottleParam[i].Wc1=(short*)memalign(8,cfg[i].ch_in*cfg[i].ch_mid*1*1*sizeof(short));
        netParam->bottleParam[i].bc1=(short*)memalign(8,cfg[i].ch_mid*sizeof(short));
        netParam->bottleParam[i].Wc2=(short*)memalign(8,cfg[i].ch_mid*3*3*sizeof(short));
        netParam->bottleParam[i].bc2=(short*)memalign(8,cfg[i].ch_mid*sizeof(short));
        netParam->bottleParam[i].Wc3=(short*)memalign(8,cfg[i].ch_out*cfg[i].ch_mid*1*1*sizeof(short));
        netParam->bottleParam[i].bc3=(short*)memalign(8,cfg[i].ch_out*sizeof(short));
    }
    //tail
    netParam->tailParam.Wc1=(short*)memalign(8,sizeof(short)*1280*320*1*1);
    netParam->tailParam.bc1=(short*)memalign(8,sizeof(short)*1280);
    netParam->tailParam.Wf1=(short*)memalign(8,sizeof(short)*1280*num_class);
    netParam->tailParam.bf1=(short*)memalign(8,sizeof(short)*num_class);
}

void SpaceDeleteq(NetParam_q* netparam){
      free(netparam->headParam.Wc1);
      free(netparam->headParam.bc1);
      free(netparam->headParam.Wc2);
      free(netparam->headParam.bc2);
      free(netparam->headParam.Wc3);
      free(netparam->headParam.bc3);
      for(int i=0;i<16;i++){
            free(netparam->bottleParam[i].Wc1);
            free(netparam->bottleParam[i].bc1);
            free(netparam->bottleParam[i].Wc2);
            free(netparam->bottleParam[i].bc2);
            free(netparam->bottleParam[i].Wc3);
            free(netparam->bottleParam[i].bc3);
      }
      free(netparam->tailParam.Wc1);
      free(netparam->tailParam.bc1);
      free(netparam->tailParam.Wf1);
      free(netparam->tailParam.bf1);
      free(netparam);
      return;
}

/*****************************************************************************/
/**
 * Load all Head, Bottleneck, and Tail parameters required by the network.
 *
 * @param paramDir is the directory prefix, including its trailing separator.
 * @param netParam is the parameter object initialized by SpaceAllocateq().
 * @param num_class is the positive number of output classes.
 *
 * @return XST_SUCCESS only when every parameter file was read completely;
 *         XST_INVALID_PARAM for invalid arguments or a missing allocation;
 *         XST_FAILURE for a truncated path, allocation, or filesystem error.
 *
 * @note Stops at the first error. The caller owns netParam and must release it
 *       with SpaceDeleteq() after failure. Local filename storage replaces the
 *       former nested stringcat_q() allocations, so no path strings leak.
 ******************************************************************************/
int ReadParamq(char *paramDir, NetParam_q *netParam, int num_class)
{
    static const int cfg[16][3] = {
        {16,96,24}, {24,144,24}, {24,144,32}, {32,192,32},
        {32,192,32}, {32,192,64}, {64,384,64}, {64,384,64},
        {64,384,64}, {64,384,96}, {96,576,96}, {96,576,96},
        {96,576,160}, {160,960,160}, {160,960,160}, {160,960,320}
    };
    static const char *const suffix[6] = {
        "wc1.bin", "bc1.bin", "wc2.bin", "bc2.bin", "wc3.bin", "bc3.bin"
    };
    char filename[160];
    int path_length;
    int status;

    if (paramDir == NULL || netParam == NULL || num_class <= 0 ||
            num_class > INT_MAX / 1280) {
        return XST_INVALID_PARAM;
    }

    /* Keep each buffer beside its file length; the arithmetic is unchanged. */
    short *head_buffers[6] = {
        netParam->headParam.Wc1, netParam->headParam.bc1,
        netParam->headParam.Wc2, netParam->headParam.bc2,
        netParam->headParam.Wc3, netParam->headParam.bc3
    };
    const int head_lengths[6] = {32*3*3*3, 32, 32*1*3*3, 32, 32*16, 16};
    short *tail_buffers[4] = {
        netParam->tailParam.Wc1, netParam->tailParam.bc1,
        netParam->tailParam.Wf1, netParam->tailParam.bf1
    };
    const int tail_lengths[4] = {1280*320, 1280, 1280*num_class, num_class};
    const char *const tail_suffix[4] = {
        "wc1.bin", "bc1.bin", "wf1.bin", "bf1.bin"
    };

    for (int j = 0; j < 6; ++j) {
        path_length = snprintf(filename, sizeof(filename), "%shead.%s",
                paramDir, suffix[j]);
        if (path_length < 0 || (size_t)path_length >= sizeof(filename)) {
            return XST_FAILURE;
        }
        status = read_param_q(head_buffers[j], head_lengths[j], filename);
        if (status != XST_SUCCESS) {
            return status;
        }
    }

    for (int i = 0; i < 16; ++i) {
        short *buffers[6] = {
            netParam->bottleParam[i].Wc1, netParam->bottleParam[i].bc1,
            netParam->bottleParam[i].Wc2, netParam->bottleParam[i].bc2,
            netParam->bottleParam[i].Wc3, netParam->bottleParam[i].bc3
        };
        const int lengths[6] = {
            cfg[i][0]*cfg[i][1], cfg[i][1], cfg[i][1]*9,
            cfg[i][1], cfg[i][2]*cfg[i][1], cfg[i][2]
        };
        for (int j = 0; j < 6; ++j) {
            path_length = snprintf(filename, sizeof(filename),
                    "%sfoldedinvertedresidual.%d.%s", paramDir, i, suffix[j]);
            if (path_length < 0 || (size_t)path_length >= sizeof(filename)) {
                return XST_FAILURE;
            }
            status = read_param_q(buffers[j], lengths[j], filename);
            if (status != XST_SUCCESS) {
                return status;
            }
        }
    }

    for (int j = 0; j < 4; ++j) {
        path_length = snprintf(filename, sizeof(filename), "%stail.%s",
                paramDir, tail_suffix[j]);
        if (path_length < 0 || (size_t)path_length >= sizeof(filename)) {
            return XST_FAILURE;
        }
        status = read_param_q(tail_buffers[j], tail_lengths[j], filename);
        if (status != XST_SUCCESS) {
            return status;
        }
    }
    return XST_SUCCESS;
}
