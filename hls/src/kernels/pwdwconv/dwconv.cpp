#include"dwconv.h"

data_t relu6(data_t x){
	if(x<(data_t)0){
		return (data_t)0;
	}
	else if(x>(data_t)6){
		return (data_t)6;
	}
	else{
		return x;
	}
}
void load_input(data_pack_t* in1,data_pack_t* in2,data_t fm_in_buff[Tm][2*Tr+K-2][2*Tc+K-2],unsigned short fm_size,
		BlockID load_block,unsigned short stride){
//in[m:m+Tm][stride*fm_row:stride*fm_row+stride*Tr+K-stride][stride*fm_col:stride*fm_col+stride*Tc+K-stride]
	int fm_row=load_block.row;
	int fm_col=load_block.col;
	int m=load_block.ch;
	if(stride==1){
		for(int i=0;i<Tr+K-1;i++)
			for(int j=0;j<Tc+K-1;j++){
#pragma HLS PIPELINE
				data_pack_t tmp1=*(in1+m/4*fm_size*fm_size+(fm_row+i-P)*fm_size+(fm_col+j-P));
				data_pack_t tmp2=*(in2+(m/4+1)*fm_size*fm_size+(fm_row+i-P)*fm_size+(fm_col+j-P));
				if((fm_row+i)>=P&&(fm_row+i)<(fm_size+P)&&(fm_col+j)>=P&&(fm_col+j)<(fm_size+P)){
					for(int k=0;k<Tm/2;k++){
#pragma HLS UNROLL
						fm_in_buff[k][i][j].range(15,0)=tmp1.range(k*16+15,k*16);
						fm_in_buff[k+4][i][j].range(15,0)=tmp2.range(k*16+15,k*16);
					}
				}
				else{
					for(int k=0;k<Tm;k++){
#pragma HLS UNROLL
						fm_in_buff[k][i][j]=(data_t)0;
					}
				}
		}
	}
	else{
		 for(int i=0;i<2*Tr+K-2;i++)
			 for(int j=0;j<2*Tc+K-2;j++){
#pragma HLS PIPELINE
				 data_pack_t tmp1=*(in1+(m/4)*fm_size*fm_size+(2*fm_row+i-P)*fm_size+(2*fm_col+j-P));
				 data_pack_t tmp2=*(in2+(m/4+1)*fm_size*fm_size+(2*fm_row+i-P)*fm_size+(2*fm_col+j-P));
				 if(2*fm_row+i>=P&&2*fm_row+i<fm_size+P&&2*fm_col+j>=P&&2*fm_col+j<fm_size+P){
					 for(int k=0;k<Tm/2;k++){
#pragma HLS UNROLL
						 fm_in_buff[k][i][j].range(15,0)=tmp1.range(k*16+15,k*16);
						 fm_in_buff[k+4][i][j].range(15,0)=tmp2.range(k*16+15,k*16);
					 }
				 }
				 else{
					 for(int k=0;k<Tm;k++){
#pragma HLS UNROLL
						 fm_in_buff[k][i][j]=(data_t)0;
					 }
				 }
			 }
	}

}

void load_weight(data_t *weight,data_t wt_buff[Tm][K][K],unsigned short m){
	//
	memcpy((data_t*)wt_buff,(const data_t*)(weight+K*K*m),sizeof(data_t)*Tm*K*K);
}

void compute(data_t fm_in_buff[Tm][2*Tr+K-2][2*Tc+K-2],data_t wt_buff[Tm][K][K],data_t bias_buff[Tm],data_t fm_out_buff[Tm][Tr][Tc]
			 ,unsigned short stride){
    //
	data_t tmp;
	for(int kx=0;kx<K;kx++)
		for(int ky=0;ky<K;ky++)
			for(int i=0;i<Tr;i++)
				for(int j=0;j<Tc;j++){
#pragma HLS PIPELINE
					for(int ch=0;ch<Tm;ch++){
						if(kx==0&&ky==0)
							tmp=bias_buff[ch];
						else
							tmp=fm_out_buff[ch][i][j];
                        tmp+=fm_in_buff[ch][i*stride+kx][j*stride+ky]*wt_buff[ch][kx][ky];
                        fm_out_buff[ch][i][j]=tmp;
					}
				}
}

void store_output(data_pack_t *out1,data_pack_t* out2,data_t fm_out_buff[Tm][Tr][Tc],unsigned fm_size,BlockID store_block,unsigned short stride){
	int fm_row=store_block.row;
	int fm_col=store_block.col;
	int m=store_block.ch;
	int o_fm_size;
	if(stride==1)
		o_fm_size=fm_size;
	else
		o_fm_size=fm_size/2;
	int base_addr1=m/4*o_fm_size*o_fm_size+fm_row*o_fm_size+fm_col;
	int base_addr2=(m/4+1)*o_fm_size*o_fm_size+fm_row*o_fm_size+fm_col;
	data_pack_t tmp1,tmp2;
	for(int i=0;i<Tr;i++)
		for(int j=0;j<Tc;j++)
		{
#pragma HLS PIPELINE
			for(int k=0;k<Tm/2;k++){
#pragma HLS UNROLL
				tmp1.range(k*16+15,k*16)=(relu6(fm_out_buff[k][i][j])).range(15,0);
				tmp2.range(k*16+15,k*16)=(relu6(fm_out_buff[k+4][i][j])).range(15,0);
			}
			*(out1+base_addr1+i*o_fm_size+j)=tmp1;
			*(out2+base_addr2+i*o_fm_size+j)=tmp2;
		}
}

void update_block(int fm_size,BlockID &block){
#pragma HLS INLINE
	//update load
	if(block.col+Tc>=fm_size){
		if(block.row+Tr>=fm_size){
			block.ch=block.ch+Tm;
			block.row=0;
			block.col=0;
		}
		else{
			block.row=block.row+Tr;
			block.col=0;
		}
	}
	else{
		block.col+=Tc;
	}
}

void update_three_block(int fm_size,BlockID &load_block,BlockID &com_block,BlockID &store_block){
	update_block(fm_size,load_block);
	update_block(fm_size,com_block);
	update_block(fm_size,store_block);
}

void load_wrapper(data_pack_t* in1,data_pack_t* in2,data_t* weight,
		          data_t wt_buff[Tm][K][K],data_t fm_in_buff[Tm][2*Tr+K-2][2*Tc+K-2],
		          unsigned short fm_size,BlockID load_block,unsigned short stride){
#pragma HLS INLINE off
	load_weight(weight,wt_buff,load_block.ch);
    load_input(in1,in2,fm_in_buff,fm_size,load_block,stride);
}
void dwconv(data_pack_t *in1,data_pack_t* in2,data_t *weight,data_t*bias,data_pack_t* out1,data_pack_t* out2,int channel,int fm_size,int stride){
//#pragma HLS INTERFACE s_axilite port=stride bundle=CTRL
//#pragma HLS INTERFACE s_axilite port=fm_size bundle=CTRL
//#pragma HLS INTERFACE s_axilite port=channel bundle=CTRL
//#pragma HLS INTERFACE m_axi depth=12544 port=out1 offset=slave bundle=OUT1 max_read_burst_length=64
//#pragma HLS INTERFACE m_axi depth=12544 port=out2 offset=slave bundle=OUT2 max_read_burst_length=64
//#pragma HLS INTERFACE m_axi depth=16 port=bias offset=slave bundle=W max_read_burst_length=256
//#pragma HLS INTERFACE m_axi depth=144 port=weight offset=slave bundle=W max_read_burst_length=256
//#pragma HLS INTERFACE m_axi depth=4*56*56 port=in1 offset=slave bundle=IN1
//#pragma HLS INTERFACE m_axi depth=4*56*56 port=in2 offset=slave bundle=IN2
//#pragma HLS INTERFACE s_axilite port=return bundle=CTRL
    //
	int o_fm_size;
	if(stride==1)
		o_fm_size=fm_size;
	else
		o_fm_size=fm_size/2;
	data_t fm_in_buff1[Tm][Tr*2+K-2][Tc*2+K-2];
	data_t fm_in_buff2[Tm][Tr*2+K-2][Tc*2+K-2];
#pragma HLS ARRAY_PARTITION variable=fm_in_buff2 complete dim=1
#pragma HLS ARRAY_PARTITION variable=fm_in_buff1 complete dim=1
	data_t wt_buff1[Tm][K][K];
	data_t wt_buff2[Tm][K][K];
#pragma HLS ARRAY_PARTITION variable=wt_buff2 complete dim=1
#pragma HLS ARRAY_PARTITION variable=wt_buff1 complete dim=1
	data_t fm_out_buff1[Tm][Tr][Tc];
	data_t fm_out_buff2[Tm][Tr][Tc];
#pragma HLS ARRAY_PARTITION variable=fm_out_buff2 complete dim=1
#pragma HLS ARRAY_PARTITION variable=fm_out_buff1 complete dim=1
	data_t bias_buff[MAX_LEN/Tm][Tm];
#pragma HLS ARRAY_PARTITION variable=bias_buff complete dim=2
	memcpy((data_t*)bias_buff,(const data_t*)bias,sizeof(data_t)*channel);
	//
	bool pp=true;
	BlockID load_block,com_block,store_block;
	//阶段1
	load_block.ch=0;
	load_block.row=0;
	load_block.col=0;
	load_wrapper(in1,in2,weight,wt_buff1,fm_in_buff1,fm_size,load_block,stride);
	//阶段2
	update_block(o_fm_size,load_block);
	com_block.ch=0;
	com_block.row=0;
	com_block.col=0;
	compute(fm_in_buff1,wt_buff1,bias_buff[com_block.ch/Tm],fm_out_buff1,stride);
	load_wrapper(in1,in2,weight,wt_buff2,fm_in_buff2,fm_size,load_block,stride);
	//
	update_block(o_fm_size,load_block);
	update_block(o_fm_size,com_block);
	store_block.ch=0;
	store_block.row=0;
	store_block.col=0;
	while(1){
#pragma HLS LOOP_TRIPCOUNT min=62 max=62 avg=62
		if(load_block.ch+Tm>channel)
			break;
		if(pp){
			load_wrapper(in1,in2,weight,wt_buff1,fm_in_buff1,fm_size,load_block,stride);
			compute(fm_in_buff2,wt_buff2,bias_buff[com_block.ch/Tm],fm_out_buff2,stride);
			store_output(out1,out2,fm_out_buff1,fm_size,store_block,stride);
		    pp=false;
		}
		else{
			load_wrapper(in1,in2,weight,wt_buff2,fm_in_buff2,fm_size,load_block,stride);
			compute(fm_in_buff1,wt_buff1,bias_buff[com_block.ch/Tm],fm_out_buff1,stride);
			store_output(out1,out2,fm_out_buff2,fm_size,store_block,stride);
			pp=true;
		}
		update_three_block(o_fm_size,load_block,com_block,store_block);
	}
    if(pp){
    	compute(fm_in_buff2,wt_buff2,bias_buff[com_block.ch/Tm],fm_out_buff2,stride);
    	store_output(out1,out2,fm_out_buff1,fm_size,store_block,stride);
    	//
    	update_three_block(o_fm_size,load_block,com_block,store_block);
    	store_output(out1,out2,fm_out_buff2,fm_size,store_block,stride);
    }
    else{
    	compute(fm_in_buff1,wt_buff1,bias_buff[com_block.ch/Tm],fm_out_buff1,stride);
    	store_output(out1,out2,fm_out_buff2,fm_size,store_block,stride);
        //
    	update_three_block(o_fm_size,load_block,com_block,store_block);
    	store_output(out1,out2,fm_out_buff1,fm_size,store_block,stride);
    }
}
