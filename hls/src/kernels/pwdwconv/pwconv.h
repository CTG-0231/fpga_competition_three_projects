#include<ap_fixed.h>
#include<ap_int.h>
#include<string.h>
#define Tp 196
#define Tn 4
#define Tm 16
#define MAX_LEN 1024
typedef ap_fixed<16,6,AP_RND,AP_SAT> data_t;
typedef ap_int<64> data_pack_t;
//typedef short data_t;
void pwconv(data_pack_t* in,data_pack_t* weight1,data_pack_t *weight2,data_t* bias,data_pack_t* out,
		    unsigned short N,unsigned short M,unsigned short SIZE,unsigned short ACT);



