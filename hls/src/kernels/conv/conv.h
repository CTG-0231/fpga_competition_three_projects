#include<ap_fixed.h>
#include<cstring>
#define N 224
#define P 1
#define K 3
#define S 2
#define Tr 28
#define Tc 28
#define Tm 8
#define Tn 3

typedef ap_fixed<16,6,AP_RND,AP_SAT> data_t;
typedef ap_int<64> data_pack_t;

void conv(data_t* in1,data_t* in2,data_t* in3,data_t* weight,data_t* bias,data_pack_t* out);

data_t relu6(data_t x);
