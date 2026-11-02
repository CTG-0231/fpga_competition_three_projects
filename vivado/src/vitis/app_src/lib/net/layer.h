#include"pl_conv.h"
#include"sd_io.h"

typedef struct {
    short *Wc1;
    short *Wc2;
    short *Wc3;
    short *bc1;
    short *bc2;
    short *bc3;
}HeadParam_q;

typedef struct {
    short *Wc1;
    short *Wc2;
    short *Wc3;
    short *bc1;
    short *bc2;
    short *bc3;
}BottleneckParam_q;

typedef struct {
    short *Wc1;
    short *bc1;
    short *Wf1;
    short *bf1;
}TailParam_q;

typedef struct {
    HeadParam_q headParam;
    BottleneckParam_q bottleParam[16];
    TailParam_q tailParam;
}NetParam_q;

typedef struct{
    int ch_in;
    int ch_mid;
    int ch_out;
    int h;
    int w;
    int stride;
}Cfg_q;

void SpaceAllocateq(NetParam_q* netParam,int num_class);

void SpaceDeleteq(NetParam_q* netparam);

/* Returns the first load error; all parameter files are required for success. */
int ReadParamq(char* paramDir,NetParam_q* netParam,int num_class);

void Bottlenecksq(short* in,BottleneckParam_q *param,short* out,Cfg_q config);

void Headq(short* in,HeadParam_q *param,short* out);

void Tailq(short* in,TailParam_q *param,short* out,int num_class);

void pwconvq(short* in,short* weight,short* bias,short* out,int ch_in,int ch_out,int h,int w);

void dwconvq(short* in,short* weight,short* bias,short* out,int stride,int h,int w,int channel);
