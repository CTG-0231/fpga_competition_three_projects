#include"fc.h"
#include<iostream>
using namespace std;

void fcq(data_t *in,data_t *w,data_t *b,data_t *out,int nin,int nout){
    int i,j;
    for(i=0;i<nout;i++){
        data_t tmp=(data_t)0;
        for(j=0;j<nin;j++){
            data_t mult=(w[i*nin+j])*(in[j]);
            tmp+=mult;
        }
        out[i]=tmp+b[i];
    }
}

void avgpoolq(data_t* in,data_t* out,int channel,int h,int w){
    for(int m=0;m<channel;m++)
    {
            data_t tmp=0.0;
            for(int i=0;i<h;i++)
                for(int j=0;j<w;j++){
                    tmp+=in[m*h*w+i*w+j];
                }
            out[m]=tmp*((data_t)(1/49.0));
    }
}

void baseline(data_t *in,data_t* weight,data_t* bias,data_t* out){
	data_t tmp[1280];
	avgpoolq(in,tmp,1280,7,7);
	fcq(tmp,weight,bias,out,1280,N);
}

void interleave(data_t *x,data_t *y,int h,int w,int ch){
    for(int n=0;n<ch/4;n++){
    	for(int i=0;i<h*w;i++){
    		y[n*4*h*w+i*4+0]=x[(n*4+0)*h*w+i];
    		y[n*4*h*w+i*4+1]=x[(n*4+1)*h*w+i];
    		y[n*4*h*w+i*4+2]=x[(n*4+2)*h*w+i];
    		y[n*4*h*w+i*4+3]=x[(n*4+3)*h*w+i];
    	}
    }
}

int main(){
    data_t in[1280*7*7];
    data_t weight[N*1280];
    data_t bias[N];
    data_t in_interleaved[1280*7*7];
    data_t out1[N];
    data_t out2[N];
    for(int i=0;i<1280*7*7;i++){
    	in[i]=(data_t)((rand()%4096-2048)/2048.0);
    }
    for(int i=0;i<1280*N;i++){
    	weight[i]=(data_t)((rand()%10000-5000)/6400.0);
    }
    for(int i=0;i<N;i++){
    	bias[i]=(data_t)((rand()%1000-500)/512.0);
    }
    interleave(in,in_interleaved,7,7,1280);
    baseline(in,weight,bias,out1);
    fc(in_interleaved,weight,bias,out2);
    for(int i=0;i<N;i++){
    	cout<<out1[i]<<","<<out2[i]<<endl;
    }
    return 0;
}
