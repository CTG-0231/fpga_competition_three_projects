#include"conv.h"
#include<iostream>
using namespace std;


void random(data_t* x,int length){
	for(int i=0;i<length;i++){
		x[i]=(data_t)(((i*i*i-5*i*i+7*i+13)%100000-50000)/50000.0);
		//cout<<x[i]<<endl;
	}
}
int main(){
	data_t* in=(data_t*)malloc(sizeof(data_t)*3*224*224+512);
	data_t* weight=(data_t*)malloc(sizeof(data_t)*32*27);
	data_t* bias=(data_t*)malloc(sizeof(data_t)*32);
	data_t* out=(data_t*)malloc(sizeof(data_t)*32*112*112);
	data_t* golden_out=(data_t*)malloc(sizeof(data_t)*32*112*112);
	random((data_t*)in,3*224*224);
    random((data_t*)weight,32*27);
    random((data_t*)bias,32);
    //
    for(int i=0;i<112;i++)
    	for(int j=0;j<112;j++)
    		for(int m=0;m<32;m++){
    			data_t tmp=bias[m];
    			for(int n=0;n<3;n++)
    				for(int kx=0;kx<K;kx++)
    					for(int ky=0;ky<K;ky++){
    						int row=i*S+kx-P;
    						int col=j*S+ky-P;
    						if(row>=0&&row<N&&col>=0&&col<N)
    							tmp+=in[n*N*N+row*N+col]*weight[m*3*3*3+n*3*3+kx*3+ky];
    					}
    			golden_out[m*112*112+i*112+j]=relu6(tmp);
    		}
    //
    conv((data_t*)in,(data_t*)in,(data_t*)in,(data_t*)weight,(data_t*)bias,(data_pack_t*)out);
    //
    for(int i=0;i<32*112*112;i++){
    	int ch=i/(112*112);
    	int pixaddr=i%(112*112);
    	int offset=(ch/4)*112*112*4+pixaddr*4+ch%4;
    	if(*(golden_out+i)!=*(out+offset))
    		return -1;
    	cout<<*(golden_out+i)<<","<<*(out+offset)<<endl;          //out[8][112][112][4]
    }
    return 0;
}
