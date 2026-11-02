//#include"pwdwconv.h"
//#define C 16
//#define N 56
//#define S 2
//
//using namespace std;
////��֧��stride=1,2��3x3��paddingΪ1�ľ���
//data_t baselinerelu6(data_t x){
//	if(x<(data_t)0)
//		return (data_t)0;
//	else if(x>(data_t)6)
//		return (data_t)6;
//	else
//		return x;
//}
//
//void baselinedwconv(data_t* in,data_t* weight,data_t* bias,data_t* out,int stride,int h,int w,int channel){
//    int p=1;
//    int k=3;
//    int h_o=(h+2*p-k)/stride+1;
//    int w_o=(w+2*p-k)/stride+1;
//    //printf("h_o=%d,w_o=%d\n",h_o,w_o);
//    for(int m=0;m<channel;m++)
//        for(int i=0;i<h_o;i++)
//            for(int j=0;j<w_o;j++){
//                data_t tmp=bias[m];
//                for(int kx=0;kx<k;kx++)
//                    for(int ky=0;ky<k;ky++)
//                       if(i*stride+kx-p>=0&&i*stride+kx-p<h&&j*stride+ky-p>=0&&j*stride+ky-p<w)
//                            tmp+=(*(in+m*h*w+(i*stride+kx-p)*w+(j*stride+ky-p)))*(*(weight+m*k*k+kx*k+ky));
//                *(out+m*h_o*w_o+i*w_o+j)=baselinerelu6(tmp);
//    }
//}
//
//
//
//void random_init(data_t* x,int length){
//	for(int i=0;i<length;i++){
//		x[i]=(data_t)(((i*i*i-2*i*i+7*i)%1024-512)/512.0);
//	}
//}
//
//void interleave(data_t in[C][N][N],data_t out[C/4][N][N][4]){
//	for(int m=0;m<C;m+=4)
//		for(int i=0;i<N;i++)
//			for(int j=0;j<N;j++){
//				for(int k=0;k<4;k++)
//					out[m/4][i][j][k]=in[m+k][i][j];
//			}
//}


//int main(){
//    data_t in[C][N][N];
//    data_t in_interleave[C/4][N][N][4];
//    data_t w[C][K][K];
//    data_t bias[C];
//    data_t out1[C][N][N];
//    data_t out1_interleave[C/4][N][N][4]; //
//    data_t golden_out1[C][N][N];
//    data_t out2[C][N/2][N/2];
//    data_t out2_interleave[C/4][N/2][N/2][4];
//    data_t golden_out2[C][N/2][N/2];
//
//	random_init((data_t*)in,C*N*N);
//	random_init((data_t*)w,C*K*K);
//	random_init((data_t*)bias,C);
//	interleave(in,in_interleave);
//    if(S==1){
//    	baselinedwconv((data_t*)in,(data_t*)w,(data_t*)bias,(data_t*)golden_out1,S,N,N,C);
//    	//dwconv((data_pack_t*)in_interleave,(data_pack_t*)in_interleave,(data_t*)w,(data_t*)bias,(data_pack_t*)out1_interleave,(data_pack_t*)out1_interleave,C,N,S);
//    	pwdwconv((data_pack_t*)in_interleave,(data_pack_t*)in_interleave,(data_pack_t*)out1_interleave,(data_pack_t*)out1_interleave,
//    			(data_t*)w,(data_t*)bias,C,C,S,N,1,0);
//    }
//    else{
//    	baselinedwconv((data_t*)in,(data_t*)w,(data_t*)bias,(data_t*)golden_out2,S,N,N,C);
//    	//dwconv((data_pack_t*)in_interleave,(data_pack_t*)in_interleave,(data_t*)w,(data_t*)bias,(data_pack_t*)out2_interleave,(data_pack_t*)out2_interleave,C,N,S);
//    	pwdwconv((data_pack_t*)in_interleave,(data_pack_t*)in_interleave,(data_pack_t*)out2_interleave,(data_pack_t*)out2_interleave,
//    	    	(data_t*)w,(data_t*)bias,C,C,S,N,1,0);
//    }
//    if(S==1){
//    	for(int i=0;i<N;i++)
//    		for(int j=0;j<N;j++)
//    			for(int m=0;m<C;m++)
//    				if(golden_out1[m][i][j]!=out1_interleave[m/4][i][j][m%4])
//    					return -1;
//    				else
//    					cout<<golden_out1[m][i][j]<<","<<out1_interleave[m/4][i][j][m%4]<<endl;
//    }
//    else{
//		for(int i=0;i<N/2;i++)
//			for(int j=0;j<N/2;j++)
//				for(int m=0;m<C;m++)
//					if(golden_out2[m][i][j]!=out2_interleave[m/4][i][j][m%4])
//						return -1;
//					else
//					    cout<<golden_out2[m][i][j]<<","<<out2_interleave[m/4][i][j][m%4]<<endl;
//    }
//    return 0;
//}
