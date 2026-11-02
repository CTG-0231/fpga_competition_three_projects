#include <ap_fixed.h>
#include <iostream>
int main() {
    typedef ap_fixed<16,6,AP_RND,AP_SAT> data_t;
    data_t half_lsb = (data_t)(1.0 / 2048.0);
    data_t minus_half_lsb = (data_t)(-1.0 / 2048.0);
    data_t sat = (data_t)40;
    data_t reciprocal = (data_t)(1.0 / 49.0);
    std::cout << sizeof(data_t) << " " << half_lsb.range(15,0).to_uint()
              << " " << minus_half_lsb.range(15,0).to_uint()
              << " " << sat.range(15,0).to_uint()
              << " " << reciprocal.range(15,0).to_uint() << std::endl;
    return 0;
}
