#include<ap_fixed.h>
#include<ap_int.h>

typedef ap_fixed<16,6,AP_RND,AP_SAT> data_t;

typedef ap_int<64> data_pack_t;

void shortcut(data_pack_t* src1,data_pack_t* src2,data_pack_t* dest,int length);
