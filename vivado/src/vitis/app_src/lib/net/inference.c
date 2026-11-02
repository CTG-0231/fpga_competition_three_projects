#include"inference.h"
#include "xiltimer.h"

Cfg_q cfg[16]={{16,96,24,112,112,2},
				  {24,144,24,56,56,1},
				  {24,144,32,56,56,2},
				  {32,192,32,28,28,1},
				  {32,192,32,28,28,1},
				  {32,192,64,28,28,2},
				  {64,384,64,14,14,1},
				  {64,384,64,14,14,1},
				  {64,384,64,14,14,1},
				  {64,384,96,14,14,1},
				  {96,576,96,14,14,1},
				  {96,576,96,14,14,1},
				  {96,576,160,14,14,2},
				  {160,960,160,7,7,1},
				  {160,960,160,7,7,1},
				  {160,960,320,7,7,1}};
short __attribute__((aligned(8))) buffer1[1500000];
short __attribute__((aligned(8))) buffer2[1500000];

void inference_q(short* in,NetParam_q* netParam,short* out,int num_class){
    Headq(in,&netParam->headParam,buffer1);
    for(int i=0;i<16;i++){
        if(i%2==0){
                Bottlenecksq(buffer1,&netParam->bottleParam[i],buffer2,cfg[i]);
        }
        else
                Bottlenecksq(buffer2,&netParam->bottleParam[i],buffer1,cfg[i]);
    }
    Tailq(buffer1,&netParam->tailParam,out,num_class);
}

