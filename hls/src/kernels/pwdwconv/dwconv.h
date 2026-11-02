#include<ap_fixed.h>
#include<cstring>
#include<iostream>

#define Tm 8
#define Tr 7
#define Tc 7
#define K 3
#define P 1
#define MAX_LEN 1024

using namespace std;

typedef ap_fixed<16,6,AP_RND,AP_SAT> data_t;
typedef ap_int<64> data_pack_t;
typedef struct{
	int ch;
	int row;
	int col;
}BlockID;                                         //块编号,表示OUT[ch:ch+Tm][row:row+Tr][col:col+Tc]


void dwconv(data_pack_t *in1,data_pack_t* in2,data_t *weight,data_t* bias,data_pack_t* out1,data_pack_t* out2,int channel,int fm_size,int stride);
