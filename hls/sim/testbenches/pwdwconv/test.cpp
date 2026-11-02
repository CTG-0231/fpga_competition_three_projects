#include"pwdwconv.h"
#include<iostream>
#include<time.h>
#include<cstring>
using namespace std;

#define C_in 16
#define C_out 24
#define Nin 28
#define Nout Nin

void interleave(data_t in[C_in][Nin][Nin],data_t out[C_in/4][Nin][Nin][4]){
	for(int n=0;n<C_in;n+=4)
		for(int i=0;i<Nin;i++)
			for(int j=0;j<Nin;j++)
				for(int k=0;k<4;k++){
					out[n/4][i][j][k]=in[n+k][i][j];
				}
}

data_t baselinerelu6(data_t x){
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
data_t in[C_in][Nin][Nin];
data_t in_interleave[C_in/4][Nin][Nin][4];
data_t weight[C_out][C_in];
data_t bias[C_out];
data_t out[C_out][Nout][Nout];
data_t out_interleave[C_out/4+16][Nout][Nout][4];
data_t exp_out[C_out][Nout][Nout];

int main(){
    int r,c,i,j,m,n;
    for(n=0;n<C_in;n++)
    	for(i=0;i<Nin;i++)
    		for(j=0;j<Nin;j++)
    		{
    			in[n][i][j]=((n+2*i-3*j)%100+10)/75.0;
    		}
    for(m=0;m<C_out;m++)
    	for(n=0;n<C_in;n++)
    		{
    			weight[m][n]=((m*2-n)%100-50)/55.0;
    		}
    for(m=0;m<C_out;m++){
    	bias[m]=((m*m-3*m)%10-5)/7.0;
    }
    //CONV BASELINE
    for(r=0;r<Nout;r++)
        for(c=0;c<Nout;c++)
            for(m=0;m<C_out;m++)
            {
                exp_out[m][r][c]=bias[m];
                for(n=0;n<C_in;n++)
                {
                    exp_out[m][r][c]+=(in[n][r][c]*weight[m][n]);
                }
                exp_out[m][r][c]=baselinerelu6(exp_out[m][r][c]);
            }
    interleave(in,in_interleave);
    //TEST
    pwdwconv((data_pack_t*)in_interleave,(data_pack_t*)weight,(data_pack_t*)weight,(data_pack_t*)out_interleave,(data_t *)bias,(data_t*)bias,
    		      C_in,C_out,1,Nin,1,1);
    //pwconv((data_pack_t*)in_interleave,(data_pack_t*)weight,(data_pack_t*)weight,(data_t*)bias,(data_pack_t*)out_interleave,C_in,C_out,Nin,0);
	for(int m=0;m<C_out;m++)
		for(int r=0;r<Nout;r++)
			for(int c=0;c<Nout;c++){
			    cout<<exp_out[m][r][c]<<","<<out_interleave[m/4][r][c][m%4]<<endl;
				if(exp_out[m][r][c]!=out_interleave[m/4][r][c][m%4]){
					cout<<"test failed!"<<endl;
					return -1;
				}
			}
	cout<<"test pass!"<<endl;
    return 0;
}


