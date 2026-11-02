#include"shortcut.h"
#include<iostream>
using namespace std;

int main(){
	data_t a[10000];
	data_t b[10000];
	data_t c[10000];
	for(int i=0;i<10000;i++){
		a[i]=(data_t)((rand()%10000-5000)/4096.0);
		b[i]=(data_t)4.0-a[i];
	}
	shortcut((data_pack_t*)a,(data_pack_t*)b,(data_pack_t*)c,10000);
	for(int i=0;i<10000;i++){
		cout<<c[i]<<endl;
	}
}
