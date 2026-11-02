#include"fc.h"

void load_feature(data_t* in,data_t fm_in_buff[32],int n){
	//读取in[n:n+32][:][:]
	data_t buff[8][49][4];
#pragma HLS ARRAY_PARTITION variable=buff complete dim=2
	data_t psum1[24];
	data_t psum2[12];
	data_t psum3[6];
	data_t psum4[3];
	data_t psum5[2];
//#pragma HLS ARRAY_PARTITION variable=buff complete dim=3
	//
	memcpy((void*)buff,(const void*)(in+n*7*7),sizeof(data_t)*Tn*7*7);
	for(int i=0;i<8;i++){
		for(int k=0;k<4;k++){
#pragma HLS PIPELINE
			for(int t=0;t<24;t++){
//#pragma HLS PIPELINE
				psum1[t]=buff[i][t][k]+buff[i][t+24][k];
			}
			for(int t=0;t<12;t++){
//#pragma HLS PIPELINE
				psum2[t]=psum1[t]+psum1[t+12];
			}
			for(int t=0;t<6;t++){
//#pragma HLS PIPELINE
				psum3[t]=psum2[t]+psum2[t+6];
			}
			for(int t=0;t<3;t++){
//#pragma HLS PIPELINE
				psum4[t]=psum3[t]+psum3[t+3];
			}
			psum5[0]=psum4[0]+psum4[1];
			psum5[1]=psum4[2]+buff[i][48][k];
			fm_in_buff[i*4+k]=(psum5[0]+psum5[1])*((data_t)(1/49.0));
	    }
	}
}


void load_weight(data_t* weight,data_t wt_buff[N][Tn],int n){
	for(int i=0;i<N;i++)
		for(int j=0;j<Tn;j++){
#pragma HLS PIPELINE II=1
			wt_buff[i][j]=*(weight+i*1280+n+j);
		}
}

void compute(data_t fm_in_buff[Tn],data_t wt_buff[N][Tn],data_t out[N]){
	for(int i=0;i<N;i++){
		for(int j=0;j<Tn;j++){
#pragma HLS PIPELINE
			out[i]+=fm_in_buff[j]*wt_buff[i][j];
		}
	}
}

void fc(data_t* in,data_t* weight,data_t* bias,data_t *out){
#pragma HLS INTERFACE s_axilite port=return bundle=CTRL
#pragma HLS INTERFACE m_axi depth=5 port=out offset=slave bundle=O
#pragma HLS INTERFACE m_axi depth=5 port=bias offset=slave bundle=W max_read_burst_length=256
#pragma HLS INTERFACE m_axi depth=6400 port=weight offset=slave bundle=W max_read_burst_length=256
#pragma HLS INTERFACE m_axi depth=62720 port=in offset=slave bundle=IN max_read_burst_length=256
    data_t out_buff[N];
#pragma HLS ARRAY_PARTITION variable=out_buff complete dim=1
    data_t fm_in_buff1[Tn];
    data_t wt_buff1[N][Tn];
    data_t fm_in_buff2[Tn];
    data_t wt_buff2[N][Tn];
    //
    for(int i=0;i<N;i++){
#pragma HLS PIPELINE
    	out_buff[i]=*(bias+i);
    }
    //
    bool pp=true;
    load_feature(in,fm_in_buff1,0);
    load_weight(weight,wt_buff1,0);
    for(int n=Tn;n<1280;n+=Tn){
    	if(pp){
    		load_feature(in,fm_in_buff2,n);
    		load_weight(weight,wt_buff2,n);
    		compute(fm_in_buff1,wt_buff1,out_buff);
    		pp=false;
    	}
    	else{
    		load_feature(in,fm_in_buff1,n);
			load_weight(weight,wt_buff1,n);
			compute(fm_in_buff2,wt_buff2,out_buff);
			pp=true;
    	}
    }
    if(pp){
    	compute(fm_in_buff1,wt_buff1,out_buff);
    }
    else{
    	compute(fm_in_buff2,wt_buff2,out_buff);
    }
    memcpy((void*)out,(const void*)out_buff,sizeof(data_t)*N);
}
