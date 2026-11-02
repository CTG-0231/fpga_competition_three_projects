#include<ap_fixed.h>
#include<cstring>
#define Tn 32
#define N 6                                        //输出类别�?
typedef ap_fixed<16,6,AP_RND,AP_SAT> data_t;
//typedef float data_t;
void fc(data_t* in,data_t* weight,data_t* bias,data_t *out);
