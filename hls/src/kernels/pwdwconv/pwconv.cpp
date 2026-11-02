#include"pwconv.h"

data_t relu6(data_t x,unsigned short ACT){
	if(ACT==1){
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
	else{
		return x;
	}
}

void load_input(data_t fm_in_buff[Tn][Tp],data_pack_t* in,unsigned short n,unsigned short basePixAddr,unsigned short fm_size,bool flag){
//load input tile In[n:n+Tn][basePixAddr:basePixAddr+Tp]
    unsigned short nn;
    unsigned short i;
    int length;
    if(flag){
    	length=49;
    }
    else{
    	length=Tp;
    }
    for(i=0;i<length;i++){
#pragma HLS PIPELINE
    	data_pack_t tmp=*(in+(n/4)*fm_size*fm_size+basePixAddr+i);
    	for(int k=0;k<4;k++){
#pragma HLS UNROLL
    		fm_in_buff[k][i].range(15,0)=tmp.range(16*k+15,16*k);
    	}
    }
}

void load_weight(data_t wt_buff[Tm][Tn],data_pack_t* weight1,data_pack_t* weight2,unsigned short n,
		         unsigned short m,unsigned short channel_in,unsigned short channel_out){
//load weight tile W[m:m+Tm][n:n+Tn]
	data_pack_t tmp1,tmp2;
    unsigned short mm,nn,rr,cc;
    for(mm=0;mm<Tm;mm+=2){
#pragma HLS PIPELINE II=1
        	tmp1=*(weight1+(m+mm)*channel_in/4+(n/4));
        	tmp2=*(weight2+(m+mm+1)*channel_in/4+(n/4));
        	for(int k=0;k<4;k++){
#pragma HLS UNROLL
        		wt_buff[mm][k].range(15,0)=tmp1.range(k*16+15,k*16);
        		wt_buff[mm+1][k].range(15,0)=tmp2.range(k*16+15,k*16);
        	}
        }
}

void compute(data_t fm_in_buff[Tn][Tp],data_t fm_out_buff[Tm][Tp],data_t wt_buff[Tm][Tn],data_t bias_buff[Tm],bool flag){
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=1
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2
#pragma HLS ARRAY_PARTITION variable=fm_out_buff complete dim=1
#pragma HLS ARRAY_PARTITION variable=fm_in_buff complete dim=1
    unsigned short i,nn,mm;
    data_t tmp;
    int length;
    if(flag)
    	length=49;
    else
    	length=Tp;
	for(i=0;i<length;i++){
		#pragma HLS PIPELINE II=1
			for(mm=0;mm<Tm;mm++){
				for(nn=0;nn<Tn;nn++){
					tmp=fm_out_buff[mm][i];
					tmp+=fm_in_buff[nn][i]*wt_buff[mm][nn];
					fm_out_buff[mm][i]=tmp;
				}
			}
		}
}

void load_bias(data_t fm_out_buff[Tm][Tp],data_t bias_buff[MAX_LEN/Tm][Tm],unsigned short m,bool flag){
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=bias_buff complete dim=2
    unsigned short mm,i;
    int length;
    if(flag)
    	length=49;
    else
    	length=Tp;
    for(i=0;i<length;i++){
#pragma HLS PIPELINE II=1
    		for(mm=0;mm<Tm;mm++){
                fm_out_buff[mm][i]=bias_buff[m/16][mm];
    		}
    	}
}

void store_output(data_t fm_out_buff[Tm][Tp],data_pack_t* out,unsigned short basePixAddr,
		          unsigned short m,unsigned short fm_size,int ACT,bool flag,unsigned short ch_out){
//store fm_out_buff to Out[m:m+Tm][basePixAddr:basePixAddr+Tp]
//store Out[m/4:m/4+4][basePixAddr:basePixAddr+Tp][:]
    unsigned short i;
    data_pack_t tmp;
    int length;
    if(flag)
    	length=49;
    else
    	length=Tp;
    int max_ch=(Tm<(ch_out-m))?Tm:(ch_out-m);                      //ch_out-m
    for(int mm=0;mm<max_ch;mm+=4)
    	for(i=0;i<length;i++){
#pragma HLS PIPELINE
    	    for(int k=0;k<4;k++)
    	    {
#pragma HLS UNROLL
    	    	tmp.range(16*k+15,16*k)=(relu6(fm_out_buff[mm+k][i],ACT)).range(15,0);
    	    }
    		*(out+((m+mm)/4)*fm_size*fm_size+basePixAddr+i)=tmp;
    	}
}


void compute_output(data_t fm_out_buff[Tm][Tp],data_t bias_buff[MAX_LEN/Tm][Tm],data_pack_t* in,data_pack_t* weight1,data_pack_t* weight2,
					unsigned short m,unsigned short fm_size,unsigned short channel_in,unsigned short channel_out,unsigned short basePixAddr,bool flag){
#pragma HLS ARRAY_PARTITION variable=bias_buff complete dim=2
		data_t fm_in_buff1[Tn][Tp];
	#pragma HLS ARRAY_PARTITION variable=fm_in_buff1 complete dim=1
	    data_t fm_in_buff2[Tn][Tp];
	#pragma HLS ARRAY_PARTITION variable=fm_in_buff2 complete dim=1
	    data_t wt_buff1[Tm][Tn];
	#pragma HLS ARRAY_PARTITION variable=wt_buff1 complete dim=2
	#pragma HLS ARRAY_PARTITION variable=wt_buff1 complete dim=1
	    data_t wt_buff2[Tm][Tn];
	#pragma HLS ARRAY_PARTITION variable=wt_buff2 complete dim=2
	#pragma HLS ARRAY_PARTITION variable=wt_buff2 complete dim=1
		unsigned short ti=0;
//calc Out[m:m+Tm][basePixAddr:basePixAddr+Tp]
		load_bias(fm_out_buff,bias_buff,m,flag);
		load_input(fm_in_buff1,in,ti,basePixAddr,fm_size,flag);
		load_weight(wt_buff1,weight1,weight2,ti,m,channel_in,channel_out);
		bool pingpong=true;             //
		for(ti=Tn;ti<channel_in;ti+=Tn){
#pragma HLS LOOP_TRIPCOUNT min=19 max=19 avg=19
			if(pingpong){          //
				load_input(fm_in_buff2,in,ti,basePixAddr,fm_size,flag);
				load_weight(wt_buff2,weight1,weight2,ti,m,channel_in,channel_out);
				compute(fm_in_buff1,fm_out_buff,wt_buff1,bias_buff[m/Tm],flag);
				pingpong=false;
			}
			else{
				load_input(fm_in_buff1,in,ti,basePixAddr,fm_size,flag);
				load_weight(wt_buff1,weight1,weight2,ti,m,channel_in,channel_out);
				compute(fm_in_buff2,fm_out_buff,wt_buff2,bias_buff[m/Tm],flag);
				pingpong=true;
			}
		}
		if(pingpong)
				compute(fm_in_buff1,fm_out_buff,wt_buff1,bias_buff[m/Tm],flag);
		else
				compute(fm_in_buff2,fm_out_buff,wt_buff2,bias_buff[m/Tm],flag);
}

void next_block(unsigned short fm_size,unsigned channel,
		        unsigned short basePixAddr,unsigned short baseChannel,
		        unsigned short &next_basePixAddr,unsigned short &next_baseChannel){
    if(basePixAddr+Tp>=fm_size*fm_size){
    	next_basePixAddr=0;
    	next_baseChannel=baseChannel+Tm;
    }
    else{
    	next_basePixAddr=basePixAddr+Tp;
    	next_baseChannel=baseChannel;
    }
}

void pwconv(data_pack_t* in,data_pack_t* weight1,data_pack_t* weight2,data_t* bias,data_pack_t* out,
		    unsigned short N,unsigned short M,unsigned short SIZE,unsigned short ACT){
//#pragma HLS INTERFACE m_axi depth=1960 port=in offset=slave bundle=IN max_read_burst_length=256
//#pragma HLS INTERFACE m_axi depth=960*160/4 port=weight1 offset=slave bundle=W1
//#pragma HLS INTERFACE m_axi depth=960*160/4 port=weight2 offset=slave bundle=W2
//#pragma HLS INTERFACE m_axi depth=960 port=bias offset=slave bundle=B max_read_burst_length=256
//#pragma HLS INTERFACE m_axi depth=11760 port=out offset=slave bundle=OUT max_write_burst_length=256
//#pragma HLS INTERFACE s_axilite port=return bundle=CTRL
//#pragma HLS INTERFACE s_axilite port=N      bundle=CTRL
//#pragma HLS INTERFACE s_axilite port=M      bundle=CTRL
//#pragma HLS INTERFACE s_axilite port=SIZE   bundle=CTRL
//#pragma HLS INTERFACE s_axilite port=ACT  bundle=CTRL
//IN,W,B,OUT
    unsigned short basePixAddr,baseChannel;
    unsigned short next_basePixAddr,next_baseChannel;
    data_t bias_buff[MAX_LEN/Tm][Tm];
#pragma HLS ARRAY_PARTITION variable=bias_buff complete dim=2
    data_t fm_out1[Tm][Tp];
#pragma HLS ARRAY_PARTITION variable=fm_out1 complete dim=1
    data_t fm_out2[Tm][Tp];
#pragma HLS ARRAY_PARTITION variable=fm_out2 complete dim=1
    //
    bool flag=((SIZE==7)?true:false);
    //
    bool pingpong;
    memcpy((data_t*)bias_buff,(const data_t*)bias,sizeof(data_t)*M);
    //
    pingpong=true;
    basePixAddr=0;
    baseChannel=0;
    next_basePixAddr=Tp;
    next_baseChannel=0;
    compute_output(fm_out1,bias_buff,in,weight1,weight2,baseChannel,SIZE,N,M,basePixAddr,flag);
    while(true){
#pragma HLS LOOP_TRIPCOUNT min=119 max=119 avg=119
    	next_block(SIZE,M,basePixAddr,baseChannel,next_basePixAddr,next_baseChannel);
    	if(pingpong){
    		compute_output(fm_out2,bias_buff,in,weight1,weight2,next_baseChannel,SIZE,N,M,next_basePixAddr,flag);
    		store_output(fm_out1,out,basePixAddr,baseChannel,SIZE,ACT,flag,M);
    		pingpong=false;
    	}
    	else{
    		compute_output(fm_out1,bias_buff,in,weight1,weight2,next_baseChannel,SIZE,N,M,next_basePixAddr,flag);
    		store_output(fm_out2,out,basePixAddr,baseChannel,SIZE,ACT,flag,M);
    		pingpong=true;
    	}
    	basePixAddr=next_basePixAddr;
    	baseChannel=next_baseChannel;
    	if(basePixAddr+Tp>=SIZE*SIZE&&baseChannel+Tm>=M)              //last block has been computed!!
    		break;
    }
    if(pingpong){
		store_output(fm_out1,out,basePixAddr,baseChannel,SIZE,ACT,flag,M);
    }
    else{
		store_output(fm_out2,out,basePixAddr,baseChannel,SIZE,ACT,flag,M);
    }
}


