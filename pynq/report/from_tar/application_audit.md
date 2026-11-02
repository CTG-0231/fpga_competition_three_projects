# Vitis 应用与模型审计

审计对象：`original/vitis_trash/Trash_LCD_OV5640/src`、`Lib/Net`、`Lib/OV5640`、`Lib/LCD`，以及导出的 HLS 驱动寄存器头和 `Trash_OV5640` BSP。以下把源代码视为证据；没有执行原工程脚本。

## 功能与真实任务

工程名和权重目录仍叫 `Trash` / `trash_weight`，但当前 `src/mess.c` 的有效模型是六类水稻叶片分类。类别索引必须保持：

| 索引 | 原标签 |
|---|---|
| 0 | healthy |
| 1 | bacterial_leaf_blight |
| 2 | brown_spot |
| 3 | leaf_blast |
| 4 | leaf_scald |
| 5 | narrow_brown |

注释中的玉米类别没有生效。原程序没有检测框、病斑分割或多目标检测；`Detecting` 是对整幅 224×224 图像分类。输出是六个有符号 `short` 原始分数，按最大值选类别；相等时取最小索引，没有 softmax 和置信阈值。

`main.c` 初始化 UART、I²C、LCD/GT911、OV5640、SD 和 HLS IP。主循环预览相机，提供识别、补光开关和采样三个触控按钮。按识别调用一次推理；采样按钮一次保存一帧到采样内存，累计 **50 次** 后才写入 `Test/camera_samples.bin`，总大小 7,526,400 字节；并非按一次就自动连续采 50 帧。推理时没有持续重新对焦，AF 只在相机初始化末尾触发。

## 输入转换的精确定义

依据 `OV5640_GetInferenceFrame` 的可执行代码：

- 采集帧：224×224×3、交错 BGR888、每行 672 字节、每帧 150,528 字节。
- HLS 输入：RGB 三平面 CHW、int16、150,528 个元素、301,056 字节。
- `R_q = trunc0((R * 2048 - 255 * 1024) / 255)`。
- `G_corrected = floor(G * 200 / 256)`，然后用同一公式量化；B 同 R。
- `trunc0` 表示 C 整数除法的向零截断，Python `//` 对负数不等价。
- R/B 实际范围 -1024…1024；当前 G 补偿下白色 G 输出 574。注释“0 至 1024”已经过期。
- 无 resize、中心裁剪、ImageNet mean/std 或额外颜色调整。改变这些会改变模型输入，不能当作等价移植。

移植实现 `src/trash_pynq/model.py::preprocess_bgr` 只接受明确的 uint8 BGR 224×224 帧。关闭 G 衰减可显式传 `256, 256`；默认忠实保留原 200/256。

## 网络执行与权重

原代码是折叠参数的 MobileNetV2：

1. Head：3×224² → Conv 32×112² → DW(32,112,stride1) → PW 16×112²；末 PW 不激活。
2. 16 个 inverted residual，配置直接来自 `Lib/Net/inference.c`。
3. Tail：PW 320×7² → 1280×7²，然后将完整 1280×7² 交给 FC IP。C 端没有另作均值池化；后续补充的 HLS 源确认 FC 内含池化，组件数值对照见文末新增证据。完整网络的板上输出仍未在本次对照。
4. 一次完整推理共 63 次 HLS 调用：Conv 1、PW 34、DW 17、shortcut 10、FC 1。

每个 bottleneck 的流程：PW 扩展、DW、PW 线性投影；仅 stride=1 且输入输出通道相同时加 shortcut。投影使用独立临时区，shortcut 不进行输入输出原址覆盖。

| block | in | mid | out | 输入边长 | stride |
|---|---:|---:|---:|---:|---:|
| 0 | 16 | 96 | 24 | 112 | 2 |
| 1 | 24 | 144 | 24 | 56 | 1 |
| 2 | 24 | 144 | 32 | 56 | 2 |
| 3–4 | 32 | 192 | 32 | 28 | 1 |
| 5 | 32 | 192 | 64 | 28 | 2 |
| 6–8 | 64 | 384 | 64 | 14 | 1 |
| 9 | 64 | 384 | 96 | 14 | 1 |
| 10–11 | 96 | 576 | 96 | 14 | 1 |
| 12 | 96 | 576 | 160 | 14 | 2 |
| 13–14 | 160 | 960 | 160 | 7 | 1 |
| 15 | 160 | 960 | 320 | 7 | 1 |

`ReadParamq` 需要 **106 个 little-endian float32 文件**，合计 2,214,502 个元素、8,858,008 字节。载入后 `float32 * 1024`、向零截断转 int16，CMA 权重数据合计 4,429,004 字节，不含每次 CMA 分配页对齐开销。`read_param_q` 没有转置、重排或 BN 计算，移植也必须保持导出文件的顺序。C 文件本身不能证明每个卷积核的内部打包次序；不能直接以普通 PyTorch/ONNX 张量替换这些 bin。

精确文件与长度可从 `weight_specs()` 取得：

| 组 | 文件 | 元素数 |
|---|---|---:|
| Head | Wc1 / bc1 | 864 / 32 |
| Head | Wc2 / bc2 | 288 / 32 |
| Head | Wc3 / bc3 | 512 / 16 |
| FoldedInvertedResidual.i | Wc1 / bc1 | in×mid / mid |
| FoldedInvertedResidual.i | Wc2 / bc2 | mid×9 / mid |
| FoldedInvertedResidual.i | Wc3 / bc3 | out×mid / out |
| Tail | Wc1 / bc1 | 409600 / 1280 |
| Tail | Wf1 / bf1 | 7680 / 6 |

文件名格式 `Head.Wc1.bin`、`FoldedInvertedResidual.0.Wc1.bin`、`Tail.Wf1.bin`，大小写和索引均有意义。第一轮仅收到 Vitis 包时未找到这 106 个权重；后续新增 python_trash 包已补齐，详见文末新增证据，原先的权重缺失限制已解除。移植 loader 在 CMA 分配前统一检查缺失、长度、NaN/Inf 与 Q10 溢出，失败绝不随机填充。C 的越界 float→short 转换没有可移植定义，因此这种文件被明确拒绝。

## HLS MMIO 接口

以下为原 BSP/驱动值，最终上板应与选定 bit/hwh 交叉确认，不能用不同平台导出的头文件替代硬件描述。所有下列地址实参和控制值均为 32 bit；缓冲地址必须来自 `allocate().device_address`。

| IP | 原基地址 | 参数偏移 |
|---|---|---|
| conv | 0x43C00000 | in1=0x10,in2=0x18,in3=0x20,weight=0x28,bias=0x30,out=0x38 |
| fc | 0x43C10000 | in=0x10,weight=0x18,bias=0x20,out=0x28 |
| pwdwconv | 0x43C20000 | PBUS1=0x10,PBUS2=0x18,PBUS3=0x20,PBUS4=0x28,SBUS1=0x30,SBUS2=0x38,ch_in=0x40,ch_out=0x48,stride=0x50,fsize=0x58,act=0x60,mode=0x68 |
| shortcut | 0x43C30000 | src1=0x10,src2=0x18,dest=0x20,length=0x28 |

公共控制：AP_CTRL=0x00、GIE=0x04、IER=0x08、ISR=0x0C；AP_START bit0、AP_DONE bit1、AP_IDLE bit2、AP_READY bit3、AUTO_RESTART bit7。C 调用只写 start、阻塞轮询 done；PYNQ 必须增加超时。

`pl_conv` 的 in1/in2/in3 都给同一输入基址，没有在 CPU 端加通道偏移。PW mode=1：PBUS1=input、PBUS2=weight、PBUS3=weight、PBUS4=output、SBUS1=bias、SBUS2=bias，stride=1，act 按网络层设置。DW mode=0：PBUS1=input、PBUS2=input、PBUS3=output、PBUS4=output、SBUS1=weight、SBUS2=bias，ch_in=ch_out，act=1。不要按端口名自行重解释这些连线。

激活使用 7 块可复用连续内存，数据合计 4,566,032 字节：input 150528、stateA/stateB 各200704、expand 1204224、depth 451584、projection 75264、output 8 个 int16。depth 最大值来自第 1 个 residual block 的 144×56²，不是 Head 的 32×112²。输出分配 8 个 short 容纳完整 64-bit 总线写节拍，只返回前 6 个分数。

每个新分配的 buffer 先归零并 flush；kernel 开始前由 kernel 层同步其输入/输出，完成后 invalidate 输出；slice 必须保持 PynqBuffer 和物理地址，不能把普通 numpy 数组地址写进寄存器。若任何 kernel 超时，Runner 锁定并保留激活内存；先停止/复位 PL，再显式 `close(assume_hardware_stopped=True)`。传入权重由调用方持有，正常 `close()` 不释放权重，故障时同样不能提前释放。

## 相机、LCD 与触控契约

- OV5640 使用 PS I²C1，原基址 0xE0005000、7-bit slave 0x3C、16-bit 寄存器地址、最终时钟40kHz。ID 寄存器0x300A/0x300B必须读0x56/0x40。
- 复位写0x3008=0x82，等10ms，待机0x42，写 `OV5640.h::Reg_Init` 全表，最后0x3008=0x02、等10ms。0x4300=0x6F配置RGB565低字节先出，PL负责后续打包/扩展，不能把传感器总线直接当BGR888。
- 自动对焦固件从0x8000下载、块64字节；主命令0x3022，ACK0x3023，状态0x3029，idle0x70/focused0x10；轮询5ms、超时2s。具体命令顺序以 `OV5640_AF_*` 源码为准。
- 补光：先0x3016=0x02、0x301C=0x02，再0x3019=0x02打开或0x00关闭。测试图案0x503D=0/0x80/0x82，0x4741=0。
- VDMA 原基址0x43000000，同时服务相机S2MM和LCD MM2S，不可初始化相机时重置整个VDMA导致LCD停掉。
- LCD 为800×480 BGR888，原预览逻辑位置(352,16)、缩放2，`LCD_FLIP_DISPLAY=1` 将所有绘制旋转180°。
- GT911 走I²C0（0xE0004000）、slave0x5D，复位GPIO54、INT GPIO0；状态0x814E、首点0x8150。Linux GPIO/I²C设备号需从实际设备树枚举，不能照抄裸机编号。
- 原 DDR 定义的起址是0x00100000。源码LCD offset0x12000000、相机offset0x12300000、采样offset0x12400000，实际物理地址分别为0x12100000、0x12400000、0x12500000；部分源码注释省略了这个基址。Linux 必须换成动态 CMA 分配。

## 已发现的问题与验证边界

1. `main` 没有检查 `CameraDetection_Init` 返回值；HLS 初始化函数只打印失败且不传播；读参数函数不检查读取状态，短文件也不检查实际 br。可能继续运行未初始化权重。移植改为集中校验并抛出明确错误。
2. 原 HLS polling 没有超时，死锁会冻结界面。故障不能通过随意释放输入输出缓冲“恢复”。
3. 函数名 `run_triple_frame_buffer` 不代表实际有三槽。当前所审 BSP 的 NUM_FSTORES=1，相机持续覆盖同一缓冲，原 `GetInferenceFrame` 也明确不冻结，存在帧撕裂。需按所选HWH实现一致快照，不能把 memcpy 当冻结。
4. `vdma_api_ov5640.c` 的相机行字节数错误依赖 **MM2S** stream width。所审 BSP 写MM2S=16、S2MM=8，与当前BGR888注释及672字节行长不一致；可能来自旧平台头文件，必须以被加载的 bit/hwh/实际PL数据通路决定行宽。不能仅照旧C的计算式移植。
5. `stringcat_q` 的嵌套分配从不释放；整体静态临时区较大。Python 使用固定路径和有界激活内存，加载权重一次、重复推理不反复分配。
6. `Check_Botten` 的 `LCD_FLIP_DISPLAY=0` 分支修改全局Detect_Flag却未返回值，且被其他按钮调用。当前默认宏为1，另一分支仍是潜在bug。
7. `Debug/camera_frame.bin` 的大小602112字节是4×150528，不能无依据地当成单幅224BGR黄金输入。旧相机输入测试还使用0…1024公式，没有当前均值偏移和G补偿，不能当当前源码的黄金标准。
8. 第一轮缺权重与训练导出工具的限制已由新增 python_trash 包解除；仍未取得可确认同帧的Vitis六分数黄金输出和实体板远程连接，因而本轮主机验证不能独立证明板上分类精度、HLS位精确输出、真实吞吐或外设电气连接已经通过。用户另已确认原版工程在其硬件上能够正常使用。

## 已运行的主机验证

`sim/test_model.py` 共8项测试通过。包含原C公式的小型fixture，用本机GCC编译执行，对0…255全部输入逐值比较三通道预处理，以及float32乘1024后short转换；原 `inference.c` 配置表和 `mess.c` 标签自动比对；106文件的缺失汇总、长度/非有限/溢出校验、分配失败回收；63次 kernel 的缓冲尺寸和地址保留、重复推理复用及超时保留内存。

测试的虚拟 kernel 只验证调度、形状和生命周期，**不模拟HLS数值**。上板还需用同一原始图像、同一实际权重逐层/最终六分数与Vitis黄金输出对比，再测试摄像头、LCD、触控、灯光和连续运行。


## 新增 hls / trash / python_trash 资料后的补充（2026-10-23）

### 用户约束与原版保留

用户明确说明原工程能够正常运行，并要求 **不修改 HLS**。因此 `src/hls` 的12个源文件已经全部恢复为 `original/hls` 的逐字节副本，逐文件 SHA256 见 `report/hls_source_integrity.json`。没有硬件修复补丁，没有强制重综合要求。`build/rebuild_hls.tcl` 只是可选的原源码0.0身份导出脚本，不是迁移所必需的步骤，未运行该脚本或替换用户既有bitstream。以下源码观察只记录证据和验证边界，不以静态推断否定用户实测结果，也不据此阻断原版运行。

### 模型文件与预处理得到确认

`original/python_trash/runs/rice/trash_weight` 已找到全部106个真实float32文件，已原样复制到 `data/trash_weight`。逐个检查了文件长度、SHA256、有限值和int16 Q10转换范围，总8,858,008字节。`data/model_manifest.json` 包含每文件hash、元素数、数值范围与预处理语义；没有重新训练、随机替代、限幅或覆盖原导出。

`runs/rice/classes.json` 的0…5类序与Vitis有效标签完全一致，只多了排序用的00_…05_前缀。`preprocessing.json` 是RGB、224×224、双线性resize且antialias、mean/std全0.5，即[-1,1]。导出代码的卷积布局与HLS索引一致：普通卷积OIHW、PW[out,in]、DW[channel,ky,kx]、FC[6,1280]，BN在导出前折叠。

**训练metadata未规定G×200/256。** 该衰减只存在于目前Vitis摄像头代码，保留默认值用于软件迁移等价；模型准确率应分别评估其影响，不能把这个板载校准参数写成训练契约。已有224×224摄像头帧不应再次resize；外部任意尺寸图片才需要按训练metadata决定resize策略。

Python包的`Out.bin`和`Infer.bin`虽然长度分别符合原始BGR帧和Q10输入，但试用G gain 200/256和256/256均无法逐值匹配。不能假设它们来自同一帧，不能把它们当作可验证的输入/输出黄金对。应记录历史样本hash，另外用明确同一次采集构建黄金对。

### 真实HLS类型与内存布局

四个IP的有效类型均是 `ap_fixed<16,6,AP_RND,AP_SAT>`：有符号16bit、整数位6（含符号）、小数位10，每次赋值/累加按AP_RND舍入并饱和。不能用“整层float卷积后统一量化”或“int32累加到最后才量化”冒充位精确参考。权重从float文件进入内存时仍按裸机C向零截断，和HLS运算阶段的AP_RND是不同环节。

Conv输入为RGB CHW；Conv输出、所有PW/DW输入输出、shortcut以及FC输入为 **[C/4,H,W,4]**。每个64bit字低16bit是组内channel0，依次到channel3。现移植调度把PL中间buffer原样传递，没有在中途做numpy CHW reshape，故不需改变model/kernel接口。若后续观察中间特征或做CPU参考，必须显式解包/打包。

FC源码 `fc.h` 明确 `N=6`，不是旧的5类。部分m_axi `depth=5`/6400为旧仿真深度注释，与当前6类实际循环及7680权重元素不一致。host分配按6类真实元素数执行。

FC确实包含7×7池化：以4通道打包格式加载，49项用固定树次序相加，`psum1`…`psum5`的赋值为Q6.10，因此这些树级求和会饱和；最后`psum5[0]+psum5[1]`是位宽增长的表达式，在乘倒数前不会再被截为Q6.10；`data_t(1/49.0)`量化为21/1024。随后FC以bias初始化，按输入通道次序进行1280次饱和MAC。该算术原样保留；与PyTorch float32全局均值池化结果可能有差异，不能用训练float32正确率替代硬件定点精度。

### IP配套与静态观察

新增 `hls` 的已导出RTL与新增 `trash` Vivado BD `ipshared` 中的RTL逐文件完全相同：conv30/30、pwdwconv48/48、fc15/15、shortcut5/5。证明这四组HLS导出与所提供Vivado工程所集成IP的源文件配套；不等同于实体板上当前装载bit已做独立数值验收。

静态观察（保持原源不改）：

- PW的`MAX_LEN=1024`、bias数组为64×16，而网络Tail调用输出1280。HLS源码在该调用的`memcpy`超出声明数组大小；导出RTL `pwconv_bias_buff_tde.v`也声明每lane深64、地址宽6，需解释实际运行时的地址截断行为。用户确认原版可用，本迁移不自动更改这一实现。
- PW以16输出通道为tile；当输出24通道时，最后tile仍加载16通道weight，虽然只存有效8通道。缺失通道的加载地址会越过权重的逻辑长度，bias多余lane未初始化，但有效输出通道运算彼此独立。保留现有二进制行为，必要时以AXI/板上数据观测确认。
- Conv和DW先读取padding位置再做边界条件置0，C仿真会形成数组前后越界访问；这不必然等同于有效输出错误，但不应直接拿裸C++全网运行成功当作无越界证据。

### 本机工具与参考编译状态

找到本机Vivado2018.3的`include/ap_fixed.h`/`ap_int.h`以及GMP库；不复制vendor专有头文件，不用2018.3打开或降级2019.2 BD。已用本机MinGW g++编译并执行 `build/reference/probe.cpp`，确认 `sizeof(data_t)=2`、正半LSB舍入成1、负半LSB舍入成0、40饱和成32767、1/49常数原始值21。此项是本机vendor类型探针，不是完整网络数值验收。原HLS各自testbench使用随机数据；还需核对其退出条件与保存的C/RTL事务是否覆盖真实模型配置。

未在提供的这些项目根下找到独立LICENSE/COPYING/NOTICE文件；保留原文件归属，引用本机vendor依赖，不把无许可声明误写成开源授权。


### 原HLS组件参考的实际编译对照

`build/reference/check_components.py` 已用本机g++编译未改动的 `src/hls/avgpool_fc/fc.cpp` 与 `src/hls/shortcut/shortcut.cpp`，运行 `hls_components.cpp` fixture，并与 `src/trash_pynq/reference.py` 的整数实现逐值对照，三组全部相等。记录见 `report/hls_component_reference.json`：

- shortcut 正负饱和、相消和四通道打包：`[32767,-32768,0,0,32767,-32768,1024,-1024]`。
- FC全6输入的树级饱和用例：`[1344,1344,32767,-1344,123,672]`。
- 不同通道/空间打包与混合权重用例：`[-46,51,-129,202,-29,109]`。

这一实际vendor类型对照也验证了重要细节：FC最后树和是表达式增宽后乘倒数，不应在乘前再加一次int16饱和。所有HLS归档源仍与原包hash一致。该参考仅覆盖layout/MAC/shortcut/FC组件，**没有把原PW数组边界问题通过修改源代码绕开，也没有声称完成了未改原版的全网C仿真或板上黄金输出验收**。
