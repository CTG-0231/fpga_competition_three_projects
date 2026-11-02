#include"pwdwconv.h"

//void dwconv(data_pack_t *in1,data_pack_t* in2,data_t *weight,data_t* bias,data_pack_t* out1,data_pack_t* out2,int channel,int fm_size,int stride);
//void pwconv(data_pack_t* in,data_pack_t* weight1,data_pack_t *weight2,data_t* bias,data_pack_t* out,
//		    unsigned short N,unsigned short M,unsigned short SIZE,unsigned short ACT);


void pwdwconv(data_pack_t* PBUS1,data_pack_t* PBUS2,data_pack_t* PBUS3,data_pack_t* PBUS4,data_t *SBUS1,data_t* SBUS2,
		      int ch_in,int ch_out,int stride,int fsize,int act,int mode){
#pragma HLS INTERFACE s_axilite port=return bundle=CTRL
#pragma HLS INTERFACE s_axilite port=ch_out bundle=CTRL
#pragma HLS INTERFACE s_axilite port=act bundle=CTRL
#pragma HLS INTERFACE s_axilite port=stride bundle=CTRL
#pragma HLS INTERFACE s_axilite port=fsize bundle=CTRL
#pragma HLS INTERFACE s_axilite port=ch_in bundle=CTRL
#pragma HLS INTERFACE s_axilite port=mode bundle=CTRL
#pragma HLS INTERFACE m_axi depth=100 port=SBUS1 offset=slave bundle=SBUS1 num_read_outstanding=8 max_read_burst_length=256
#pragma HLS INTERFACE m_axi depth=100 port=SBUS2 offset=slave bundle=SBUS2 num_read_outstanding=8 max_read_burst_length=256
#pragma HLS INTERFACE m_axi depth=100 port=PBUS1 offset=slave bundle=PBUS1 num_read_outstanding=8 max_read_burst_length=256 max_write_burst_length=256
#pragma HLS INTERFACE m_axi depth=100 port=PBUS2 offset=slave bundle=PBUS2 num_read_outstanding=8 max_read_burst_length=256 max_write_burst_length=256
#pragma HLS INTERFACE m_axi depth=100 port=PBUS3 offset=slave bundle=PBUS3 num_read_outstanding=8 max_read_burst_length=256 max_write_burst_length=256
#pragma HLS INTERFACE m_axi depth=100 port=PBUS4 offset=slave bundle=PBUS4 num_read_outstanding=8 max_read_burst_length=256 max_write_burst_length=256
	//mode==0,dwconv,mode=1,pwconv
	if(mode==0){
		dwconv(PBUS1,PBUS2,SBUS1,SBUS2,PBUS3,PBUS4,ch_in,fsize,stride);
	}
	else{
		pwconv(PBUS1,PBUS2,PBUS3,SBUS1,PBUS4,ch_in,ch_out,fsize,act);
	}
}
