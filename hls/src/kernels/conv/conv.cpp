#include"conv.h"
#include<iostream>
using namespace std;

data_t relu6(data_t x){
	if(x<(data_t)0)
		return (data_t)0;
	else if(x>(data_t)6)
		return (data_t)6;
	else
		return x;
}
//(3,224,224)*(32,3,3,3)---->(32,112,112) stride=2
void load_input(data_t* in1,data_t* in2,data_t* in3,data_t fm_in_buff[Tn][Tr*S+K-S][Tc*S+K-S],unsigned short fm_row,unsigned short fm_col){
    //load in[:][fm_row*S:fm_row*S+S*Tr+K-S][fm_col*S+S*Tc+K-S]
		for(int i=0;i<Tr*S+K-S;i++)
			for(int j=0;j<Tc*S+K-S;j++){
#pragma HLS PIPELINE II=1
				data_t tmp1=*(in1+(2*fm_row+i-P)*N+(2*fm_col+j-P));
				data_t tmp2=*(in2+N*N+(2*fm_row+i-P)*N+(2*fm_col+j-P));
				data_t tmp3=*(in3+2*N*N+(2*fm_row+i-P)*N+(2*fm_col+j-P));
				if(2*fm_row+i>=P&&2*fm_row+i<N+P&&2*fm_col+j>=P&&2*fm_col+j<N+P){
					fm_in_buff[0][i][j]=tmp1;
					fm_in_buff[1][i][j]=tmp2;
					fm_in_buff[2][i][j]=tmp3;
				}
				else{
					fm_in_buff[0][i][j]=(data_t)0;
					fm_in_buff[1][i][j]=(data_t)0;
					fm_in_buff[2][i][j]=(data_t)0;
				}
			}
}

void load_weight(data_t* weight,data_t wt_buff[Tm][Tn][K][K],unsigned short m){
	//load weight[m:m+Tm][:][:][:]
    memcpy((data_t*)wt_buff,(const data_t*)(weight+m*27),sizeof(data_t)*Tm*27);
}

void store_output(data_pack_t* out,data_t fm_out_buff[Tm][Tr][Tc],unsigned short m,unsigned short fm_row,unsigned short fm_col){
	//store out[Tm][fm_row:fm_row+Tr][fm_col:fm_col+Tc]
	data_pack_t tmp;
	for(int mm=0;mm<Tm;mm+=4){
		for(int i=0;i<Tr;i++)
			for(int j=0;j<Tc;j++){
#pragma HLS PIPELINE II=1
				for(int k=0;k<4;k++){
#pragma HLS UNROLL
					tmp.range(16*k+15,16*k)=(relu6(fm_out_buff[k+mm][i][j])).range(15,0);
				}
				*(out+((m+mm)/4)*112*112+(fm_row+i)*112+fm_col+j)=tmp;
		}
	}
}

void compute(data_t fm_in_buff[Tn][S*Tr+K-S][S*Tc+K-S],data_t wt_buff[Tm][Tn][K][K],
		     data_t bias_buff[Tm],data_t fm_out_buff[Tm][Tr][Tc]){
	static data_t tmp=0;
	for(int kx=0;kx<K;kx++)
		for(int ky=0;ky<K;ky++)
			for(int i=0;i<Tr;i++)
				for(int j=0;j<Tc;j++){
#pragma HLS PIPELINE II=1
					for(int mm=0;mm<Tm;mm++){
						for(int nn=0;nn<Tn;nn++){
							if(kx==0&&ky==0&&nn==0)
							    tmp=bias_buff[mm];
							else
								tmp=fm_out_buff[mm][i][j];
							tmp+=fm_in_buff[nn][i*S+kx][j*S+ky]*wt_buff[mm][nn][kx][ky];
							fm_out_buff[mm][i][j]=tmp;
						}
					}
				}
}

void compute_output(data_t* weight,data_pack_t* out,data_t fm_in_buff[Tn][Tr*S+K-S][Tc*S+K-S],data_t bias_buff[32],int row,int col){
	data_t wt_buff[Tm][Tn][K][K];
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=1
	data_t fm_out_buff[Tm][Tr][Tc];
#pragma HLS ARRAY_PARTITION variable=fm_out_buff complete dim=1
	//
	for(int ch=0;ch<32;ch+=Tm){
	#pragma HLS DATAFLOW
		load_weight(weight,wt_buff,ch);
		compute(fm_in_buff,wt_buff,bias_buff+ch,fm_out_buff);
		store_output(out,fm_out_buff,ch,row,col);
	}
}

void next_block(int row,int col,int &next_row,int &next_col,int fsize){
	if(col+Tc>=fsize){
		next_row=row+Tr;
		next_col=0;
	}
	else{
		next_row=row;
		next_col=col+Tc;
	}
}

void conv(data_t* in1,data_t* in2,data_t *in3,data_t* weight,data_t* bias,data_pack_t* out){
#pragma HLS INTERFACE s_axilite port=return bundle=CTRL
#pragma HLS INTERFACE m_axi depth=100352 port=out offset=slave bundle=OUT max_read_burst_length=32
#pragma HLS INTERFACE m_axi depth=32 port=bias offset=slave bundle=W
#pragma HLS INTERFACE m_axi depth=864 port=weight offset=slave bundle=W
#pragma HLS INTERFACE m_axi depth=150528+512 port=in1 offset=slave bundle=IN1 max_read_burst_length=64
#pragma HLS INTERFACE m_axi depth=150528+512 port=in2 offset=slave bundle=IN2 max_read_burst_length=64
#pragma HLS INTERFACE m_axi depth=150528+512 port=in3 offset=slave bundle=IN3 max_read_burst_length=64
	//in[3][224][224],weight[32][3][3][3],bias[32]--->out[32][112][112]
    data_t fm_in_buff1[Tn][Tr*S+K-S][Tc*S+K-S];
    data_t fm_in_buff2[Tn][Tr*S+K-S][Tc*S+K-S];
#pragma HLS ARRAY_PARTITION variable=fm_in_buff1 complete dim=1
#pragma HLS ARRAY_PARTITION variable=fm_in_buff2 complete dim=1
    data_t wt_buff[Tm][Tn][K][K];
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=1
    data_t bias_buff[32];
#pragma HLS ARRAY_PARTITION variable=bias_buff complete dim=1
    data_t fm_out_buff[Tm][Tr][Tc];
#pragma HLS ARRAY_PARTITION variable=fm_out_buff complete dim=1
    memcpy((data_t*)bias_buff,(const data_t*)bias,sizeof(data_t)*32);
    //
    bool pp=true;
    int row,col,next_row,next_col;
    row=0;
    col=0;
    cout<<"加载("<<row<<","<<col<<")至fm_in_buff1"<<endl;
    load_input(in1,in2,in3,fm_in_buff1,row,col);
    while(true){
    	next_block(row,col,next_row,next_col,N/2);
    	if(pp){
    		cout<<endl;
    		cout<<"加载("<<next_row<<","<<next_col<<")至fm_in_buff2"<<endl;
    		cout<<"计算("<<row<<","<<col<<")fm_in_buff1中的输入特征"<<endl;
    		load_input(in1,in2,in3,fm_in_buff2,next_row,next_col);
    		compute_output(weight,out,fm_in_buff1,bias_buff,row,col);
    		pp=false;
    	}
    	else{
    		cout<<endl;
    		cout<<"加载("<<next_row<<","<<next_col<<")至fm_in_buff1"<<endl;
    		cout<<"计算("<<row<<","<<col<<")fm_in_buff2中的输入特征"<<endl;
    		load_input(in1,in2,in3,fm_in_buff1,next_row,next_col);
    		compute_output(weight,out,fm_in_buff2,bias_buff,row,col);
    		pp=true;
    	}
    	row=next_row;
    	col=next_col;
    	if(row+Tr>=N/2&&col+Tc>=N/2)
    		break;
    }
    cout<<endl;
    if(pp){
    	compute_output(weight,out,fm_in_buff1,bias_buff,row,col);
    	cout<<"计算("<<row<<","<<col<<")fm_in_buff1中的输入特征"<<endl;
    }
    else{
    	compute_output(weight,out,fm_in_buff2,bias_buff,row,col);
    	cout<<"计算("<<row<<","<<col<<")fm_in_buff2中的输入特征"<<endl;
    }
    /*
    for(int row=0;row<N/2;row+=Tr)
    	for(int col=0;col<N/2;col+=Tc){
    		load_input(in1,in2,in3,fm_in_buff,row,col);
    		compute_output(weight,out,fm_in_buff,bias_buff,row,col);
    	}
    */
}
