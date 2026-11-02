#include"shortcut.h"

void shortcut(data_pack_t* src1,data_pack_t* src2,data_pack_t* dest,int length){
#pragma HLS INTERFACE s_axilite port=return bundle=CTRL
#pragma HLS INTERFACE s_axilite port=length bundle=CTRL
#pragma HLS INTERFACE m_axi depth=10000/4 port=dest offset=slave bundle=OUT max_write_burst_length=256
#pragma HLS INTERFACE m_axi depth=10000/4 port=src2 offset=slave bundle=IN2 max_read_burst_length=256
#pragma HLS INTERFACE m_axi depth=10000/4 port=src1 offset=slave bundle=IN1 max_read_burst_length=256
	//dest[i]+=src[i] for i=0,1,2,....,length-1
    data_pack_t pack1;
    data_pack_t pack2;
    data_pack_t pack3;
    data_t tmp1[4];
    data_t tmp2[4];
    data_t sum[4];
	for(int i=0;i<length/4;i++){
#pragma HLS PIPELINE II=1
		pack1=*(src1+i);
		pack2=*(src2+i);
    	for(int k=0;k<4;k++){
#pragma HLS UNROLL
    		tmp1[k].range(15,0)=pack1.range(16*k+15,16*k);
    		tmp2[k].range(15,0)=pack2.range(16*k+15,16*k);
    		sum[k]=tmp1[k]+tmp2[k];
    		pack3.range(16*k+15,16*k)=sum[k].range(15,0);
    	}
    	*(dest+i)=pack3;
    	//*(dest+i)=*(src1+i)+*(src2+i);
    }
}
