// Compile against ORIGINAL HLS FC/shortcut sources and installed vendor headers.
// No source rewriting, hardware changes, or full-network claims.
#include <ap_fixed.h>
#include <ap_int.h>
#include <iostream>
#include <vector>

typedef ap_fixed<16,6,AP_RND,AP_SAT> data_t;
typedef ap_int<64> pack_t;
void fc(data_t*, data_t*, data_t*, data_t*);
void shortcut(pack_t*, pack_t*, pack_t*, int);

int raw(data_t value) {
    unsigned bits = value.range(15,0).to_uint();
    return bits >= 32768 ? (int)bits - 65536 : (int)bits;
}
data_t fixed_raw(int value) {
    data_t result;
    result.range(15,0) = (unsigned short)value;
    return result;
}

int main() {
    int lhs[] = {32760, -32760, 1, -1, 30000, -30000, 512, -512};
    int rhs[] = {100, -100, -1, 1, 30000, -30000, 512, -512};
    pack_t a[2], b[2], result[2];
    for (int word=0; word<2; ++word) {
        for (int lane=0; lane<4; ++lane) {
            a[word].range(16*lane+15,16*lane) = (unsigned short)lhs[word*4+lane];
            b[word].range(16*lane+15,16*lane) = (unsigned short)rhs[word*4+lane];
        }
    }
    shortcut(a,b,result,8);
    std::cout << "shortcut";
    for (int word=0; word<2; ++word) {
        for (int lane=0; lane<4; ++lane) {
            data_t value;
            value.range(15,0)=result[word].range(16*lane+15,16*lane);
            std::cout << " " << raw(value);
        }
    }
    std::cout << std::endl;

    std::vector<data_t> input(1280*49), weights(6*1280), bias(6), out(6);
    for(int i=0;i<1280*49;++i) input[i]=fixed_raw(6144);
    for(int i=0;i<6*1280;++i) weights[i]=fixed_raw(0);
    for(int i=0;i<6;++i) bias[i]=fixed_raw(0);
    weights[0]=fixed_raw(1024);
    weights[1280+1279]=fixed_raw(1024);
    for(int ch=0;ch<1280;++ch) weights[2*1280+ch]=fixed_raw(1024);
    weights[3*1280]=fixed_raw(-1024);
    bias[4]=fixed_raw(123);
    weights[5*1280]=fixed_raw(512);
    fc(input.data(),weights.data(),bias.data(),out.data());
    std::cout << "fc_saturated";
    for(int i=0;i<6;++i) std::cout << " " << raw(out[i]);
    std::cout << std::endl;

    // Different constant per-channel values exercise all four packed lanes.
    for(int ch=0;ch<1280;++ch) {
        for(int pixel=0;pixel<49;++pixel) {
            int index=(ch/4)*49*4+pixel*4+ch%4;
            input[index]=fixed_raw((ch*17)%1000-500);
        }
    }
    for(int i=0;i<6*1280;++i) weights[i]=fixed_raw((i*7)%100-50);
    for(int i=0;i<6;++i) bias[i]=fixed_raw(i*31-100);
    fc(input.data(),weights.data(),bias.data(),out.data());
    std::cout << "fc_packed_pattern";
    for(int i=0;i<6;++i) std::cout << " " << raw(out[i]);
    std::cout << std::endl;
    return 0;
}
