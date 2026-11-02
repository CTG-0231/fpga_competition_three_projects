/* Independent integer Q6.10 arithmetic reference, not an HLS/AXI simulator.
 * Each original data_t assignment rounds nearest (ties to +infinity), then
 * saturates to signed16. PW reads every valid bias, including output1280.
 */
#include <stdint.h>
#include <stddef.h>

#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API
#endif

static int16_t sat(int64_t x) {
    return x > 32767 ? 32767 : x < -32768 ? -32768 : (int16_t)x;
}

static int16_t round_q20(int64_t x) {
    int64_t value = x + 512;
    /* C99 division truncates toward0; explicitly implement floor division. */
    int64_t q = value >= 0 ? value / 1024 : -((-value + 1023) / 1024);
    return sat(q);
}

static int16_t madd(int16_t acc, int16_t x, int16_t w) {
    return round_q20((int64_t)acc * 1024 + (int64_t)x * w);
}

static int16_t relu6(int16_t x) {
    return x < 0 ? 0 : x > 6144 ? 6144 : x;
}

static size_t packed(int channel, int pixel, int pixels) {
    return ((size_t)(channel / 4) * pixels + pixel) * 4 + channel % 4;
}

API void q10_conv(const int16_t *in, const int16_t *weight,
                  const int16_t *bias, int16_t *out) {
    const int pixels = 112 * 112;
    for (int m = 0; m < 32; ++m) {
        for (int r = 0; r < 112; ++r) {
            for (int c = 0; c < 112; ++c) {
                int16_t total = bias[m];
                for (int kx = 0; kx < 3; ++kx) {
                    for (int ky = 0; ky < 3; ++ky) {
                        int rr = 2 * r + kx - 1, cc = 2 * c + ky - 1;
                        for (int n = 0; n < 3; ++n) {
                            int16_t x = (rr >= 0 && rr < 224 && cc >= 0 && cc < 224)
                                ? in[n * 224 * 224 + rr * 224 + cc] : 0;
                            total = madd(total, x, weight[m * 27 + n * 9 + kx * 3 + ky]);
                        }
                    }
                }
                out[packed(m, r * 112 + c, pixels)] = relu6(total);
            }
        }
    }
}

API void q10_pw(const int16_t *in, const int16_t *weight,
                const int16_t *bias, int16_t *out,
                int ch_in, int ch_out, int act, int size) {
    int pixels = size * size;
    for (int m = 0; m < ch_out; ++m) {
        for (int p = 0; p < pixels; ++p) {
            int16_t total = bias[m];
            for (int n = 0; n < ch_in; ++n)
                total = madd(total, in[packed(n, p, pixels)], weight[(size_t)m * ch_in + n]);
            out[packed(m, p, pixels)] = act ? relu6(total) : total;
        }
    }
}

API void q10_dw(const int16_t *in, const int16_t *weight,
                const int16_t *bias, int16_t *out,
                int channels, int size, int stride) {
    int output_size = size / stride, pixels = size * size;
    int output_pixels = output_size * output_size;
    for (int n = 0; n < channels; ++n) {
        for (int r = 0; r < output_size; ++r) {
            for (int c = 0; c < output_size; ++c) {
                int16_t total = bias[n];
                for (int kx = 0; kx < 3; ++kx) {
                    for (int ky = 0; ky < 3; ++ky) {
                        int rr = r * stride + kx - 1, cc = c * stride + ky - 1;
                        int16_t x = (rr >= 0 && rr < size && cc >= 0 && cc < size)
                            ? in[packed(n, rr * size + cc, pixels)] : 0;
                        total = madd(total, x, weight[n * 9 + kx * 3 + ky]);
                    }
                }
                out[packed(n, r * output_size + c, output_pixels)] = relu6(total);
            }
        }
    }
}

API void q10_shortcut(const int16_t *in1, const int16_t *in2,
                      int16_t *out, int length) {
    for (int i = 0; i < length; ++i)
        out[i] = sat((int32_t)in1[i] + in2[i]);
}

API void q10_fc(const int16_t *in, const int16_t *weight,
                const int16_t *bias, int16_t *out) {
    int16_t averaged[1280];
    for (int n = 0; n < 1280; ++n) {
        int16_t p1[24], p2[12], p3[6], p4[3], p5[2];
        for (int t = 0; t < 24; ++t)
            p1[t] = sat((int32_t)in[packed(n, t, 49)] + in[packed(n, t + 24, 49)]);
        for (int t = 0; t < 12; ++t) p2[t] = sat((int32_t)p1[t] + p1[t + 12]);
        for (int t = 0; t < 6; ++t) p3[t] = sat((int32_t)p2[t] + p2[t + 6]);
        for (int t = 0; t < 3; ++t) p4[t] = sat((int32_t)p3[t] + p3[t + 3]);
        p5[0] = sat((int32_t)p4[0] + p4[1]);
        p5[1] = sat((int32_t)p4[2] + in[packed(n, 48, 49)]);
        /* p5[0]+p5[1] is a widened expression, not another data_t sum. */
        averaged[n] = round_q20(((int64_t)p5[0] + p5[1]) * 21);
    }
    for (int m = 0; m < 6; ++m) {
        int16_t total = bias[m];
        for (int n = 0; n < 1280; ++n)
            total = madd(total, averaged[n], weight[m * 1280 + n]);
        out[m] = total;
    }
}
